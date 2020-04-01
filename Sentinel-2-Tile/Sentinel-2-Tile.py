#------------------------------------------------------------------------------
# Copyright 2018 ArcGEO
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#------------------------------------------------------------------------------

# ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ##
#                   Sentinel-2 L2A Tile Python Raster Type
# ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ##
#Minimum Version Requirement: ArcGIS Pro 2.2

# The base path for a Sentinel-2 tile is the metadata.xml. The file must be in same directory as tileInfo.json file and the R10m, R20m and R60m folders.

import os
import json
import arcpy
from functools import lru_cache

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

ns = {'n1': 'https://psd-12.sentinel2.eo.esa.int/PSD/S2_PDI_Level-2A_Tile_Metadata.xsd', 
        'n2': 'https://psd-14.sentinel2.eo.esa.int/PSD/S2_PDI_Level-2A_Tile_Metadata.xsd',
        'nx': ''} # nx is set either to n1 or n2 depending on the processed metadata file

bandProperties = {
                  13: {'bandName': 'B00', 'bandIndex': 0, 'filename': '../qi/CLD_20m.jp2', 'wavelengthMin': 0.0, 'wavelengthMax': 0.0 },
                  0: {'bandName': 'B01', 'bandIndex': 0, 'filename': 'B01.jp2', 'wavelengthMin': 433.0, 'wavelengthMax': 453.0 },
                  1: {'bandName': 'B02', 'bandIndex': 1, 'filename': 'B02.jp2', 'wavelengthMin': 458.0, 'wavelengthMax': 522.0 },
                  2: {'bandName': 'B03', 'bandIndex': 2, 'filename': 'B03.jp2', 'wavelengthMin': 543.0, 'wavelengthMax': 577.0 },
                  3: {'bandName': 'B04', 'bandIndex': 3, 'filename': 'B04.jp2', 'wavelengthMin': 650.0, 'wavelengthMax': 680.0 },
                  4: {'bandName': 'B05', 'bandIndex': 4, 'filename': 'B05.jp2', 'wavelengthMin': 698.0, 'wavelengthMax': 712.0 },
                  5: {'bandName': 'B06', 'bandIndex': 5, 'filename': 'B06.jp2', 'wavelengthMin': 733.0, 'wavelengthMax': 747.0 },
                  6: {'bandName': 'B07', 'bandIndex': 6, 'filename': 'B07.jp2', 'wavelengthMin': 773.0, 'wavelengthMax': 793.0 },
                  7: {'bandName': 'B08', 'bandIndex': 7, 'filename': 'B08.jp2', 'wavelengthMin': 784.0, 'wavelengthMax': 899.0 },
                  8: {'bandName': 'B8A', 'bandIndex': 8, 'filename': 'B8A.jp2', 'wavelengthMin': 855.0, 'wavelengthMax': 875.0 },
                  9: {'bandName': 'B09', 'bandIndex': 9, 'filename': 'B09.jp2', 'wavelengthMin': 935.0, 'wavelengthMax': 955.0 },
                  10: {'bandName': 'B10', 'bandIndex': 10, 'filename': 'B10.jp2', 'wavelengthMin': 1360.0, 'wavelengthMax': 1390.0 },
                  11: {'bandName': 'B11', 'bandIndex': 11, 'filename': 'B11.jp2', 'wavelengthMin': 1565.0, 'wavelengthMax': 1655.0 },
                  12: {'bandName': 'B12', 'bandIndex': 12, 'filename': 'B12.jp2', 'wavelengthMin': 2100.0, 'wavelengthMax': 2280.0 }
                }
Rxm = { '10m': { 'bandKeys': [1, 2, 3, 7], 'rasterFunctionTemplate': 'Composite4Bands.rft.xml' },
        '20m': { 'bandKeys': [1, 2, 3, 4, 5, 6, 8, 11, 12], 'rasterFunctionTemplate': 'Composite9Bands.rft.xml'},
        '20c': { 'bandKeys': [13, 1, 2, 3, 4, 5, 6, 8, 11, 12], 'rasterFunctionTemplate': 'Composite10Bands.rft.xml' }  # 20m + cloudMask as band B00
}


class DataSourceType():
    Unknown = 0
    File = 1
    Folder = 2


class RasterTypeFactory():

    def getRasterTypesInfo(self):
        self.acquisitionDate_auxField = arcpy.Field()
        self.acquisitionDate_auxField.name = 'AcquisitionDate'
        self.acquisitionDate_auxField.aliasName = 'Acquisition Date'
        self.acquisitionDate_auxField.type = 'Date'
        self.acquisitionDate_auxField.length = 50

        self.sensorName_auxField = arcpy.Field()
        self.sensorName_auxField.name = 'SensorName'
        self.sensorName_auxField.aliasName = 'Sensor Name'
        self.sensorName_auxField.type = 'String'
        self.sensorName_auxField.length = 50

        self.productName_auxField = arcpy.Field()
        self.productName_auxField.name = 'ProductName'
        self.productName_auxField.aliasName = 'Product Name'
        self.productName_auxField.type = 'String'
        self.productName_auxField.length = 100

        self.cloudCoverage_auxField = arcpy.Field()
        self.cloudCoverage_auxField.name = 'CloudCoverage'
        self.cloudCoverage_auxField.aliasName = 'Cloud Coverage'
        self.cloudCoverage_auxField.type = 'Double'
        self.cloudCoverage_auxField.precision = 5

        self.vegetationPercentage_auxField = arcpy.Field()
        self.vegetationPercentage_auxField.name = 'VegetationPercentage'
        self.vegetationPercentage_auxField.aliasName = 'Vegetation Percentage'
        self.vegetationPercentage_auxField.type = 'Double'
        self.vegetationPercentage_auxField.precision = 5
        rasterTypes = [
                {
                    'rasterTypeName': 'Sentinel-2-L2A-10mTile',
                    'builderName': 'Sentinel210mTileBuilder',
                    'dataSourceType': (DataSourceType.File),
                    'dataSourceFilter': 'metadata.xml',
                    'description': ("Supports reading of Sentinel-2 Level 2A Tiles with 10m resolution."
                                    "Level 2A tile products metadata files"),
                    'supportsOrthorectification': False,
                    'enableClipToFootprint': True,
                    'isRasterProduct': True,
                    # #'crawlerName': 'Sentinel2Tile10mCrawler',
                    'productDefinitionName': 'Sentinel-2_L2A_Tile',
                    'supportedUriFilters': [
                                            {
                                                'name': 'Tile',
                                                'allowedProducts': [
                                                                    'Sentinel-2_L2A_Tile'
                                                                   ],
                                                'supportsOrthorectification': False,
                                                'supportedTemplates': [
                                                                        'Composite10mBands'
                                                                      ]
                                            }
                                           ],
                    'processingTemplates': [
                                            {
                                                'name': 'Composite10mBands',
                                                'enabled': True,
                                                'outputDatasetTag': '10m-4Band',
                                                'primaryInputDatasetTag': '10m',
                                                'isProductTemplate': True,
                                                'functionTemplate': Rxm['10m']['rasterFunctionTemplate']
                                            }                                        
                                           ],
                    'bandProperties': [bandProperties[k] for k in bandProperties if k in Rxm['10m']['bandKeys']],
                    'fields': [self.sensorName_auxField,
                               self.productName_auxField,
                               self.acquisitionDate_auxField,
                               self.cloudCoverage_auxField,
                               self.vegetationPercentage_auxField]
                },
                {
                    'rasterTypeName': 'Sentinel-2-L2A-20mTile',
                    'builderName': 'Sentinel220mTileBuilder',
                    'dataSourceType': (DataSourceType.File),
                    'dataSourceFilter': 'metadata.xml',
                    'description': ("Supports reading of Sentinel-2 Level 2A Tiles with 20m resolution."
                                    "Level 2A tile products metadata files"),
                    'supportsOrthorectification': False,
                    'enableClipToFootprint': True,
                    'isRasterProduct': True,
                    # #'crawlerName': 'Sentinel2Tile10mCrawler',
                    'productDefinitionName': 'Sentinel-2_L2A_Tile',
                    'supportedUriFilters': [
                                            {
                                                'name': 'Tile',
                                                'allowedProducts': [
                                                                    'Sentinel-2_L2A_Tile'
                                                                   ],
                                                'supportsOrthorectification': False,
                                                'supportedTemplates': [
                                                                        'Composite20mBands'
                                                                      ]
                                            }
                                           ],
                    'processingTemplates': [
                                            {
                                                'name': 'Composite20mBands',
                                                'enabled': True,
                                                'outputDatasetTag': '20m-9Band',
                                                'primaryInputDatasetTag': '20m',
                                                'isProductTemplate': True,
                                                'functionTemplate': Rxm['20m']['rasterFunctionTemplate']
                                            }
                                           ],
                    'bandProperties': [bandProperties[k] for k in bandProperties if k in Rxm['20m']['bandKeys']],
                    'fields': [self.sensorName_auxField,
                               self.productName_auxField,
                               self.acquisitionDate_auxField,
                               self.cloudCoverage_auxField,
                               self.vegetationPercentage_auxField]
                },
                {
                    'rasterTypeName': 'Sentinel-2-L2A-20mCloudTile',
                    'builderName': 'Sentinel220mCloudTileBuilder',
                    'dataSourceType': (DataSourceType.File),
                    'dataSourceFilter': 'metadata.xml',
                    'description': ("Supports reading of Sentinel-2 Level 2A Tiles with 20m resolution and cloud mask."
                                    "Level 2A tile products metadata files"),
                    'supportsOrthorectification': False,
                    'enableClipToFootprint': True,
                    'isRasterProduct': True,
                    # #'crawlerName': 'Sentinel2Tile10mCrawler',
                    'productDefinitionName': 'Sentinel-2_L2A_Tile',
                    'supportedUriFilters': [
                                            {
                                                'name': 'Tile',
                                                'allowedProducts': [
                                                                    'Sentinel-2_L2A_Tile'
                                                                   ],
                                                'supportsOrthorectification': False,
                                                'supportedTemplates': [
                                                                        'Composite20mBandsCloud'
                                                                      ]
                                            }
                                           ],
                    'processingTemplates': [
                                            {
                                                'name': 'Composite20mBandsCloud',
                                                'enabled': True,
                                                'outputDatasetTag': '20m-10Band',
                                                'primaryInputDatasetTag': '20m',
                                                'isProductTemplate': True,
                                                'functionTemplate': Rxm['20c']['rasterFunctionTemplate']
                                            }
                                           ],
                    'bandProperties': [bandProperties[k] for k in bandProperties if k in Rxm['20c']['bandKeys']],
                    'fields': [self.sensorName_auxField,
                               self.productName_auxField,
                               self.acquisitionDate_auxField,
                               self.cloudCoverage_auxField,
                               self.vegetationPercentage_auxField]
                }
               ]
        return rasterTypes


# ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ##
# Utility functions used by the Builder and Crawler classes
# ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ##


class Utilities():

    def isS2Tile(self, path):
        # check for element name
        # check for tileInfo.json
        # check for directory and jp2 files
        isS2Tile = False
        tree = cacheElementTree(path)
        if tree is not None:
            element = tree.getroot()
            if element is not None:
                isS2Tile = element.tag ==  r'{https://psd-12.sentinel2.eo.esa.int/PSD/S2_PDI_Level-2A_Tile_Metadata.xsd}Level-2A_Tile_ID'            

        return isS2Tile

    def getProductType(self, path):
        return 'Sentinel-2_L2A_Tile'

    def getProductName(self, path):
        folder, filename = os.path.split(path)
        if filename != 'metadata.xml':
            folder, parent = os.path.split(folder)
        with open(os.path.join(folder, 'tileInfo.json'), 'r') as f:
            tileInfo = json.load(f)
        if 'productName' in tileInfo:
            return tileInfo['productName']
        return None

    def getGroupName(self, path):
        folder, filename = os.path.split(path)
        if filename != 'metadata.xml':
            folder, parent = os.path.split(folder)
        with open(os.path.join(folder, 'tileInfo.json'), 'r') as f:
            tileInfo = json.load(f)
        if 'utmZone' in tileInfo and 'latitudeBand' in tileInfo and 'gridSquare' in tileInfo:
            return "T{0}{1}{2}".format(tileInfo['utmZone'], tileInfo['latitudeBand'], tileInfo['gridSquare'])
        return None

    def getDisplayName(self, path):
        prodName = self.getProductName(path)
        if prodName:
            dn = prodName.split('_')
            if len(dn)>=2:
                return dn[-2] + "_" + dn[-1]
        return None

    def getBandAngles(self, tree):
        angles = tree.find('./nx:Geometric_Info/Tile_Angles/Mean_Viewing_Incidence_Angle_List', ns)
        bandAngles = {}
        if angles is not None:
            for band_info in angles:
                bandAngle = {}
                bandAngle['SourceBandIndex'] = int(band_info.attrib['bandId'])
                zenith_angle = band_info.find('ZENITH_ANGLE')
                bandAngle['ZenithAngle'] = float(zenith_angle.text)
                azimut_angle = band_info.find('AZIMUTH_ANGLE')
                bandAngle['AzimuthAngle'] = float(azimut_angle.text)
                bandAngle['Unit'] = azimut_angle.attrib['unit']
                band_num = 0
                bandAngles[bandAngle['SourceBandIndex']] = bandAngle
        return bandAngles

# ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ##
# Sentinel 2 Tile builder class
# ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ##


class Sentinel2TileBuilder(object):

    def __init__(self, **kwargs):
        self.SensorName = 'Sentinel-2'
        self.utilities = Utilities()

    def canOpen(self, datasetPath):
        # Open the datasetPath and check if the XML metadata file contains the element Level-2A_Tile_ID
        res = self.utilities.isS2Tile(datasetPath)
        return res

    def buildResolution(self, itemURI, resolution):
        """ For resolution use one of strings  10m | 20m | 20c """
        # Make sure that the itemURI dictionary contains items

        if len(itemURI) <= 0:
            return None
        try:
            # ItemURI dictionary passed from crawler containing
            # path, tag, display name, group name, product type
            path = None
            if 'path' in itemURI:
                path = itemURI['path']
            else:
                return None

            # The metadata file is a XML file
                #set the correct namespace
            ns["nx"] = ""
            with open(path, "r") as f:
                # check first 2 lines for namespace
                for i in range(2):
                    line = f.readline()
                    ns["nx"] = ns["n1"] if ns["n1"] in line else ns["nx"]
                    ns["nx"] = ns["n2"] if ns["n2"] in line else ns["nx"]

            tree = cacheElementTree(path)
            # Horizontal CS (can also be a arcpy.SpatialReference object,
            # EPSG code, path to a PRJ file or a WKT string)
            srsEPSG = 0
            #Here, using the epsg code to build srs            
            projectionNode = tree.find('./nx:Geometric_Info/Tile_Geocoding/HORIZONTAL_CS_CODE', ns)

            if projectionNode is not None:
                srsEPSG = int((projectionNode.text).split(":")[1]) #to get EPSG code

            # Dataset frame - footprint; this is a list of Vertex coordinates from tileInfo.json
            vertex_array = arcpy.Array()
            folder, filename = os.path.split(path)
            with open(os.path.join(folder, 'tileInfo.json'), 'r') as f:
                tileInfo = json.load(f)
            if ('tileDataGeometry' in tileInfo) and ('coordinates' in tileInfo['tileDataGeometry']):
                for vertex in tileInfo['tileDataGeometry']['coordinates'][0]:
                    x_vertex = vertex[0]
                    y_vertex = vertex[1]                    
                    vertex_array.add(arcpy.Point(x_vertex, y_vertex))
            #the order of vertices must be ul, ur, lr, ll

            # Get geometry object for the footprint; the SRS of the
            # footprint can also be passed if it is different to the
            # SRS read from the metadata; by default, the footprint
            # geometry is assumed to be in the SRS of the metadata
            footprint_geometry = arcpy.Polygon(vertex_array, arcpy.SpatialReference(srsEPSG) if srsEPSG > 0 else None)

            # Other keyProperties information (Cloud Coverage, Vegeneation Percentage etc)
            keyProperties = {}
            keyProperties['Footprint'] = footprint_geometry
            keyProperties['BlockName'] = self.utilities.getGroupName(path)
            keyProperties['SensorName'] = self.SensorName
            keyProperties['ProductType'] = self.utilities.getProductType(path)
            #Set the Product Name
            if keyProperties['ProductType'] == 'Sentinel-2_L2A_Tile':
                keyProperties['ProductName'] = self.utilities.getProductName(path)
                itemURI['GroupName'] = self.utilities.getGroupName(path)
                itemURI['DisplayName'] = self.utilities.getDisplayName(path)

            # Get the acquisition date of the scene
            sensing_time = tree.find('./nx:General_Info/SENSING_TIME', ns)            
            if sensing_time is not None:
                keyProperties['AcquisitionDate'] = sensing_time.text

            quality_indi = tree.find('./nx:Quality_Indicators_Info', ns) 
            if quality_indi is not None:
                # Get the Cloud Coverage
                cloudCoverage = quality_indi.find('./L2A_Image_Content_QI/CLOUD_COVERAGE_PERCENTAGE')
                if cloudCoverage is not None:
                    keyProperties['CloudCoverage'] = float(cloudCoverage.text)
                    keyProperties['CloudCover'] = float(cloudCoverage.text)

                # Get the Sun Azimuth
                vegetationPercentage = quality_indi.find('./L2A_Image_Content_QI/VEGETATION_PERCENTAGE')
                if vegetationPercentage is not None:
                    keyProperties['VegetationPercentage'] = float(vegetationPercentage.text)

            buildItemsList = list()
            buildItem = {} 
            imparam = [os.path.join(folder, 'R'+resolution.replace("c", "m"), bandProperties[k]['filename']) for k in Rxm[resolution]['bandKeys']]

            geopos = tree.find("./nx:Geometric_Info/Tile_Geocoding/Geoposition[@resolution='" + resolution[:-1] + "']", ns)            
            for im in imparam:
                with open(im[:-3]+'j2w', "w") as wf:
                    wf.write(resolution[:-1] + "\n0\n-0\n-" + resolution[:-1] + "\n")
                    wf.write(str(int(geopos.find("ULX").text) + int(geopos.find("XDIM").text)/2) + "\n")
                    wf.write(str(int(geopos.find("ULY").text) + int(geopos.find("YDIM").text)/2) + "\n")

            rfa = {}
            for i in range(len(imparam)):
                rfa['Raster'+str(i+1)] = imparam[i]
            buildItem['raster'] = {
                'functionDataset': {
                    'rasterFunction': Rxm[resolution]['rasterFunctionTemplate'],
                    'rasterFunctionArguments': rfa
                }
            }

            ba = self.utilities.getBandAngles(tree)
            keyProperties['bandProperties'] = [{
                'BandName': bandProperties[b]['bandName'], 
                'WavelengthMin': bandProperties[b]['wavelengthMin'],
                'WavelengthMax': bandProperties[b]['wavelengthMax'],
                'SourceBandIndex': bandProperties[b]['bandIndex'], 
                'ZenithAngle': ba[bandProperties[b]['bandIndex']]['ZenithAngle'], 
                'AzimuthAngle': ba[bandProperties[b]['bandIndex']]['AzimuthAngle'],
                'Unit': ba[bandProperties[b]['bandIndex']]['Unit']
                } for b in bandProperties if b in Rxm[resolution]['bandKeys']]

            buildItem['itemURI'] = {'displayName': self.utilities.getDisplayName(path) if not (buildItemsList) else None, 
                                    'groupName': self.utilities.getGroupName(path)}
            buildItem['spatialReference'] = srsEPSG
            buildItem['footprint'] = footprint_geometry
            buildItem['keyProperties'] = keyProperties
            buildItemsList.append(buildItem)

            return buildItemsList

        except:
            print ("Exception from Builder")
            raise


class Sentinel210mTileBuilder(Sentinel2TileBuilder):

    def build(self, itemURI):
        return self.buildResolution(itemURI, '10m')

class Sentinel220mTileBuilder(Sentinel2TileBuilder):

    def build(self, itemURI):
        return self.buildResolution(itemURI, '20m')

class Sentinel220mCloudTileBuilder(Sentinel2TileBuilder):

    def build(self, itemURI):
        return self.buildResolution(itemURI, '20c')


# ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ##
# Sentinel Crawlerclass
# ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ## ----- ##


# class Sentinel2TileCrawler():

#     def __init__(self, **crawlerProperties):
#         self.utils = Utilities()
#         self.paths = crawlerProperties['paths']
#         self.recurse = crawlerProperties['recurse']
#         self.filter = '*.jp2'
#         self.currentPath = None
#         self.pathGenerator = self.createGenerator()


#     def __iter__(self):
#         return self

#     #this is a generator function
#     def createGenerator(self):
#         for p in self.paths:
#             folder, filename = os.path.split(p)
#             self.currentPath = folder
#             path = folder + '\\R20m'
#             if not os.path.exists(path):
#                 continue

#             if os.path.isdir(path):
#                 for root, dirs, files in (os.walk(path)):
#                     for file in (files):
#                         if file.endswith(".jp2") and file.startswith("B"):
#                             filename = os.path.join(root, file)
#                             yield filename
#             elif path.endswith(".jp2") and file.startswith("B"):
#                 yield path

#     def next(self):
#         ## Return URI dictionary to Builder
#         try:
#             uri = self.getNextUri()
#             print(uri['path'])
#             return uri
#         except StopIteration:
#             print("Returninmg empty dict")
#             return None
       

#     def getNextUri(self):
#         self.curPath = next(self.pathGenerator)
#         curTag = self.utils.getTag(self.curPath)
#         productName = self.utils.getProductName(self.curPath)
        
#         #If the tag or productName was not found in the metadata file or there was some exception raised, we move on to the next item
#         if curTag is None or productName is None:
#             return self.getNextUri()

#         uri = {
#                 'path': self.curPath,
#                 'displayName': os.path.basename(self.curPath),
#                 'tag': curTag,
#                 'groupName': os.path.split(os.path.dirname(self.curPath))[1],
#                 'productName': productName,
#                 'metadata': self.currentPath
#             }
#         return uri



@lru_cache(maxsize=128)
def cacheElementTree(path):
        try:
            tree = ET.parse(path)
        except ET.ParseError as e:
            print("Exception while parsing {0}\n{1}".format(path,e))
            return None

        return tree

#Using the default crawler as there is only Panchromatic band


