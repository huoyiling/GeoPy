'''
Created on Feb 11, 2015

Some utility functions related to processing datasets (to avoid code repetition)

@author: Andre R. Erler, GPL v3
'''

# external imports
import numpy as np
from importlib import import_module
from functools import partial
import yaml,os
from datetime import datetime
# internal imports
from geodata.misc import DatasetError, DateError, isInt
from utils.misc import namedTuple
from datasets.common import getFileName
# specific datasets
import datasets.WRF as WRF
import datasets.CESM as CESM


# load YAML configuration file
def loadYAML(default, lfeedback=True):
  ''' load YAML configuration file and return config object '''
  # check for environment variable
  if os.environ.has_key('PYAVG_YAML'): 
    yamlfile = os.environ['PYAVG_YAML']
    # try to guess variations, if path is not valid
    if not os.path.isfile(yamlfile): 
      if os.path.isdir(yamlfile): # use default filename in directory
        yamlfile = '{:s}/{:s}'.format(yamlfile,default)
      else: # use filename in current directory
        yamlfile = '{:s}/{:s}'.format(os.getcwd(),yamlfile)
    if lfeedback: print("\nLoading user-specified YAML configuration file:\n '{:s}'".format(yamlfile))
  else: # use default in current directory
    yamlfile = '{:s}/{:s}'.format(os.getcwd(),default)
    if lfeedback: print("\nLoading default YAML configuration file:\n '{:s}'".format(yamlfile))
  # check if file exists  
  if not os.path.exists(yamlfile): 
    raise IOError, "YAML configuration file not found!\n ('{:s}')".format(yamlfile)
  # read file
  with open(yamlfile) as f: 
    config = yaml.load(f, Loader=yaml.Loader)
  # return config object
  return config


## convenience function to load WRF experiment list and replace names with Exp objects
def getExperimentList(experiments, project, dataset, lensembles=True):
  ''' load WRF or CESM experiment list and replace names with Exp objects '''
  # load WRF experiments list
  project = 'projects' if not project else 'projects.{:s}'.format(project)
  mod = import_module('{:s}.{:s}_experiments'.format(project,dataset))
  # expand WRF experiments
  if experiments is None: # do all (with or without ensembles)
    exps, enss = mod.experiments, mod.enss; del mod # use list without shortcuts to avoid duplication
    if lensembles: experiments = [exp for exp in exps.itervalues()]  
    else: experiments = [exp for exp in exps.itervalues() if exp.shortname not in enss] 
  else: 
    exps, enss = mod.exps, mod.enss; del mod # use list with shortcuts added
    try: experiments = [exps[exp] for exp in experiments]
    except KeyError: # throw exception is experiment is not found
      raise KeyError, "{1:s} experiment '{0:s}' not found in {1:s} experiment list (loaded from '{2:s}').".format(exp,dataset,project)
  # return expanded list of experiments
  return experiments

def getPeriodGridString(period, grid, exp=None, beginyear=None):
  ''' utility function to check period and grid and return valid and usable strings '''
  # period
  if period is None: pass
  elif isinstance(period,(int,np.integer)):
    if beginyear is None: beginyear = int(exp.begindate[0:4]) # most datasets begin in 1979
    period = (beginyear, beginyear+period)
  elif len(period) != 2 and all(isInt(period)): raise DateError
  periodstr = '{0:4d}-{1:4d}'.format(*period) if period else ''
  # grid
  gridstr = grid if grid  else ''
  # return
  return periodstr, gridstr


## prepare target dataset
def getTargetFile(dataset=None, mode=None, dataargs=None, lwrite=True, grid=None, period=None, filetype=None):
  ''' generate filename for target dataset '''
  # prepare some variables
  domain = dataargs.domain
  if filetype is None: filetype = dataargs.filetype
  if grid is None: grid = dataargs.gridstr # also use grid for station type
  if period is None: period = dataargs.periodstr
  gstr = '_{}'.format(grid) if grid else ''
  pstr = '_{}'.format(period) if period else ''
  # figure out filename
  if dataset == 'WRF' and lwrite:
    if mode == 'climatology': filename = WRF.clim_file_pattern.format(filetype,domain,gstr,pstr)
    elif mode == 'time-series': filename = WRF.ts_file_pattern.format(filetype,domain,gstr)
    else: raise NotImplementedError
  elif dataset == 'CESM' and lwrite:
    if mode == 'climatology': filename = CESM.clim_file_pattern.format(filetype,gstr,pstr)
    elif mode == 'time-series': filename = CESM.ts_file_pattern.format(filetype,gstr)
    else: raise NotImplementedError
  elif ( dataset == dataset.upper() or dataset == 'Unity' ) and lwrite: # observational datasets
    filename = getFileName(grid=grid, period=dataargs.period, name=dataargs.obs_res, filetype=mode)      
  elif not lwrite: raise DatasetError
  if not os.path.exists(dataargs.avgfolder): 
    raise IOError, "Dataset folder '{:s}' does not exist!".format(dataargs.avgfolder)
  # return filename
  return filename

def getSourceAge(filelist=None, fileclasses=None, filetypes=None, exp=None, domain=None,
                 periodstr=None, gridstr=None, lclim=None, lts=None):
  ''' function to to get the latest modification date of a set of filetypes '''
  srcage = datetime.fromordinal(1) # the beginning of time (proleptic Gregorian calendar)
  # if complete file list is given, just check each file
  if filelist:
    for filepath in filelist:
      if not os.path.exists(filepath): raise IOError, "Source file '{:s}' does not exist!".format(filepath)        
      # determine age of source file
      fileage = datetime.fromtimestamp(os.path.getmtime(filepath))          
      if srcage < fileage: srcage = fileage # use latest modification date
  else:    
    # prepare period and grid strings
    periodstr = '_{}'.format(periodstr) if periodstr else ''
    gridstr = '_{}'.format(gridstr) if gridstr else ''    
    # assemble filenames from dataset arguments
    for filetype in filetypes:
      fileclass = fileclasses[filetype] # avoid WRF & CESM name collision
      if domain is None:
        if lclim: filename = fileclass.climfile.format(gridstr,periodstr) # insert grid and period
        elif lts: filename = fileclass.tsfile.format(gridstr) # insert grid
      else:
        if lclim: filename = fileclass.climfile.format(domain,gridstr,periodstr) # insert domain number, grid, and period
        elif lts: filename = fileclass.tsfile.format(domain,gridstr) # insert domain number, and grid
      filepath = '{:s}/{:s}'.format(exp.avgfolder,filename)
      if not os.path.exists(filepath): raise IOError, "Source file '{:s}' does not exist!".format(filepath)        
      # determine age of source file
      fileage = datetime.fromtimestamp(os.path.getmtime(filepath))          
      if srcage < fileage: srcage = fileage # use latest modification date
  # return latest modification date
  return srcage

## determine dataset metadata
def getMetaData(dataset, mode, dataargs, lone=True):
  ''' determine dataset type and meta data, as well as path to main source file '''
  # determine dataset mode
  lclim = False; lts = False
  if mode == 'climatology': lclim = True
  elif mode == 'time-series': lts = True
  else: raise NotImplementedError, "Unrecognized Mode: '{:s}'".format(mode)
  # general arguments (dataset independent)
  varlist = dataargs.get('varlist',None)
  grid = dataargs.get('grid',None) # get grid
  period = dataargs.get('period',None)
  # determine meta data based on dataset type
  if dataset == 'WRF': 
    # WRF datasets
    obs_res = None # only for datasets (not used here)
    exp = dataargs['experiment'] # need that one
    dataset_name = exp.name
    avgfolder = exp.avgfolder
    filetypes = dataargs['filetypes']
    domain = dataargs.get('domain',None)
    periodstr, gridstr = getPeriodGridString(period, grid, exp=exp)
    # check arguments
    if period is None and lclim: raise DatasetError, "A 'period' argument is required to load climatologies!"
    if lone and len(filetypes) > 1: raise DatasetError # process only one file at a time
    if not isinstance(domain, (np.integer,int)): raise DatasetError   
    # construct dataset message
    if lone: 
      datamsgstr = "Processing WRF '{:s}'-file from Experiment '{:s}' (d{:02d})".format(filetypes[0], dataset_name, domain)
    else: datamsgstr = "Processing WRF dataset from Experiment '{:s}' (d{:02d})".format(dataset_name, domain)       
    # figure out age of source file(s)
    srcage = getSourceAge(fileclasses=WRF.fileclasses, filetypes=filetypes, exp=exp, domain=domain,
                          periodstr=periodstr, gridstr=gridstr, lclim=lclim, lts=lts)
    # load source data
    if lclim:
      loadfct = partial(WRF.loadWRF, experiment=exp, name=None, domains=domain, grid=grid, varlist=varlist,
                        period=period, filetypes=filetypes, varatts=None, lconst=True) # still want topography...
    elif lts:
      loadfct = partial(WRF.loadWRF_TS, experiment=exp, name=None, domains=domain, grid=grid, varlist=varlist,
                        filetypes=filetypes, varatts=None, lconst=True) # still want topography...
  elif dataset == 'CESM': 
    # CESM datasets
    obs_res = None # only for datasets (not used here)
    domain = None # only for WRF
    exp = dataargs['experiment']  
    avgfolder = exp.avgfolder
    dataset_name = exp.name
    periodstr, gridstr = getPeriodGridString(period, grid, exp=exp)
    filetypes = dataargs['filetypes']
    # check arguments
    if period is None and lclim: raise DatasetError, "A 'period' argument is required to load climatologies!"
    if lone and len(filetypes) > 1: raise DatasetError # process only one file at a time
    # construct dataset message
    if lone:
      datamsgstr = "Processing CESM '{:s}'-file from Experiment '{:s}'".format(filetypes[0], dataset_name) 
    else: datamsgstr = "Processing CESM dataset from Experiment '{:s}'".format(dataset_name) 
    # figure out age of source file(s)
    srcage = getSourceAge(fileclasses=CESM.fileclasses, filetypes=filetypes, exp=exp, domain=None,
                          periodstr=periodstr, gridstr=gridstr, lclim=lclim, lts=lts)
    # load source data 
    load3D = dataargs.pop('load3D',None) # if 3D fields should be loaded (default: False)
    if lclim:
      loadfct = partial(CESM.loadCESM, experiment=exp, name=None, grid=grid, period=period, varlist=varlist, 
                        filetypes=filetypes, varatts=None, load3D=load3D, translateVars=None)
    elif lts:
      loadfct = partial(CESM.loadCESM_TS, experiment=exp, name=None, grid=grid, varlist=varlist,
                        filetypes=filetypes, varatts=None, load3D=load3D, translateVars=None)     
  elif dataset == dataset.upper() or dataset == 'Unity':
    # observational datasets
    filetypes = [None] # only for CESM & WRF
    domain = None # only for WRF
    module = import_module('datasets.{0:s}'.format(dataset))      
    dataset_name = module.dataset_name
    resolution = dataargs['resolution']
    if resolution: obs_res = '{0:s}_{1:s}'.format(dataset_name,resolution)
    else: obs_res = dataset_name   
    # figure out period
    periodstr, gridstr = getPeriodGridString(period, grid, beginyear=1979)
    if period is None and lclim: periodstr = 'LTM'
    datamsgstr = "Processing Dataset '{:s}'".format(dataset_name)
    # assemble filename to check modification dates (should be only one file)    
    filename = getFileName(grid=grid, period=period, name=obs_res, filetype=mode)
    avgfolder = module.avgfolder
    filepath = '{:s}/{:s}'.format(avgfolder,filename)
    # load pre-processed climatology
    if lclim:
      loadfct = partial(module.loadClimatology, name=dataset_name, period=period, grid=grid, 
                        varlist=varlist, resolution=resolution, varatts=None)
    elif lts:
      loadfct = partial(module.loadTimeSeries, name=dataset_name, grid=grid, varlist=varlist,
                        resolution=resolution, varatts=None)
    # check if the source file is actually correct
    if os.path.exists(filepath): filelist = [filepath]
    else:
      source = loadfct() # don't load dataset, just construct the file list
      filelist = source.filelist
    # figure out age of source file(s)
    srcage = getSourceAge(filelist=filelist, lclim=lclim, lts=lts)
      # N.B.: it would be nice to print a message, but then we would have to make the logger available,
      #       which would be too much trouble
  else:
    raise DatasetError, "Dataset '{:s}' not found!".format(dataset)
  ## assemble and return meta data
  dataargs = namedTuple(dataset_name=dataset_name, period=period, periodstr=periodstr, avgfolder=avgfolder, 
                        filetypes=filetypes,filetype=filetypes[0], domain=domain, obs_res=obs_res, 
                        varlist=varlist, grid=grid, gridstr=gridstr) 
  # return meta data
  return dataargs, loadfct, srcage, datamsgstr    


if __name__ == '__main__':
    pass