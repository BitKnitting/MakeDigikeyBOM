#
# The main entry point to making a digikey Bom CSV file from the output of bom2csv
# as discussed in the bitknitting blog post: https://bitknitting.wordpress.com/2016/03/05/from-kicad-to-digikey-generating-a-bom-based-on-esteem-overview/
#
import logging
logger = logging.getLogger(__name__)
from replaceJellyBeanParts import replaceJellyBeanParts
from makeDigikeyFile import makeDigikeyFile
from getParts import getParts

def makeDigikeyBOM(outputFrom_bom2csv,jellyBeanFile,outDir,numProcesses):
    modifiedBOM2csvFile = replaceJellyBeanParts(outputFrom_bom2csv=outputFrom_bom2csv,jellyBeanFile=jellyBeanFile)
    components_by_part_number = getParts(modifiedBOM2csvFile=modifiedBOM2csvFile)
    if not makeDigikeyFile(components_by_part_number,outDir):
        logger.error("Could not make the Digikey file.  Check output from logger.")