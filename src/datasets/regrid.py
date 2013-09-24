'''
Created on 2013-09-23

A script to reproject and resample datasets in this package onto a given grid.

@author: Andre R. Erler, GPL v3
'''

# external imports
from importlib import import_module
import os # check if files are present
# internal imports
from datasets.common import addLandMask, addLengthAndNamesOfMonth, getFileName
from geodata.process import CentralProcessingUnit
from geodata.netcdf import DatasetNetCDF

if __name__ == '__main__':
  
  # datasets to process
  datasets = ['NARR','CFSR','GPCC','CRU','PRISM']
  datasets = ['PRISM']
  # grid to project onto
  grid = 'NARR'
  # period for climatology
  period = (1979,1981)
  
  # load relevant grid definition
  grid_def = import_module(grid[0:4]).__dict__[grid+'_grid']
  print grid_def
  
  for dataset in datasets:
    
    # import dataset routines
    ds = import_module(dataset)
    if dataset == 'PRISM': loadDataset = ds.__dict__['load%s'%dataset]
    else: loadDataset = ds.__dict__['load%s_TS'%dataset] # function that loads the dataset

    periodstr = '%4i-%4i'%period
    print('\n')
    print('   ***   Processing Dataset %s from %s   ***   '%(dataset, periodstr))
    print('             (regridding from %s to %s)   '%(dataset,grid))
    print('\n')        
    
    # load source
    source = loadDataset() # varlist=['datamask','T2']
    # source.load() # not really necessary
    print(source)
    print('\n')
          
    # prepare target dataset
    filename = getFileName(grid=grid, period=period, name=dataset, filepattern=ds.avgfile)
    if os.path.exists(ds.avgfolder+filename): os.remove(ds.avgfolder+filename)
    atts =dict(period=periodstr, name=dataset, title='%s Climatology'%dataset) 
    sink = DatasetNetCDF(folder=ds.avgfolder, filelist=[filename], atts=source.atts, mode='w')
    
    # initialize processing
    CPU = CentralProcessingUnit(source, sink, tmp=True)

    if period is not None and dataset != 'PRISM':
      # determine averaging interval
      offset = source.time.getIndex(period[0]-1979)/12 # origin of monthly time-series is at January 1979 
      # start processing climatology
      CPU.Climatology(period=period[1]-period[0], offset=offset, flush=False)
    
    # get NARR coordinates
    if grid != dataset:
      # reproject and resample (regrid) dataset
      CPU.Regrid(griddef=grid_def, flush=False)

    # get results
    CPU.sync(flush=True, deepcopy=True)
      
    if 'convertPrecip' in ds.__dict__:
      # convert precip data to SI units (mm/s) 
      ds.__dict__['convertPrecip'](sink.precip) # convert in-place
    # add landmask
    addLandMask(sink) # create landmask from precip mask
    sink.mask(sink.landmask) # mask all fields using the new landmask
    # add length and names of month
    if dataset != 'PRISM': addLengthAndNamesOfMonth(sink, noleap=False) 
    
    # close...
    sink.sync()
    sink.close()
    # print dataset
    print('')
    print(sink)     
  