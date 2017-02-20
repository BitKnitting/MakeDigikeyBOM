import csv
import sys
from bs4 import BeautifulSoup
import logging
logger = logging.getLogger(__name__)
#
# Both the files outputFrom_bom2csv and jellyBeanFile were opened in __main__.py
# This function returns a file that has modified the PN field if the component within the outputFrom_bom2csv file was a Jelly Bean part.
# The return file is an intermediate file that is used as input into scraping Digikey web pages.
def replaceJellyBeanParts(outputFrom_bom2csv,jellyBeanFile):
    # Read the list of "jellybean" manufacturers parts from the Jellybean csv file.
    # ****-> I assume the csv file has three columns named Category,Value,MFR_PN
    # *** -> WARNING <- *** The last time I ran bom2csv (Feb, 2017) the names were comp_PN,Value,PN....this will fail.  This could be made more robust.  But for
    # *** Now I'll put in warning code in the debug output.o
    # (First 3 rows) Example jellybeen csv file format:
    # Category,Value,MFR_PN
    # C,.1u,CL21F104ZBCNNNC
    # C,1u,TMK212BJ105KG-T
    #
    # Create a set that contains the unique category name.  For example,
    # Capacitor is a category named 'C' ..so the parts_csvfile would have multiple parts associcated with 'C', e.g.: - 1u, .1u, etc.
    uniqueCategories = set()
    with jellyBeanFile as csvfile:
        csvReader = csv.DictReader(csvfile)
        for row in csvReader:
            try:
                uniqueCategories.add(row['Category'])
            except:
                logger.error('ERROR! Check the Jellybean csv file. Make sure header labels are Category,Value,PN') 
        # Read the BoM file created within eeSchema into Beautiful Soup
        # I noticed the kicost code used the lxml parser.  This wasn't installed on my Mac.  I saw it discussed in the Beautiful Soup documentation:
        # http://www.crummy.com/software/BeautifulSoup/bs4/doc/  (see Installing a parser).
        # I ran easy_install lxml and was treated to - Could not find function xmlCheckVersion in library libxml2. Is libxml2 installed?
        # Perhaps try: xcode-select --install ... which I guess installs XCode command line utilities?  Once I installed, the lxml parser compiled/built/installed...
        # I don't thoroughly understand the install process but it worked.... so...I continue.  More details on error installing lxml on Mac OSX is discussed:
        # http://stackoverflow.com/questions/19548011/cannot-install-lxml-on-mac-os-x-10-9
        #
        # The BoM file created by bom2csv in Kicad is in XML.  The root variable contains oll the XML that is in the file.
        root = BeautifulSoup(outputFrom_bom2csv,"lxml")
        # Some components in the schematic won't have part numbers.  These need to be removed from the root variable.
        #
        # if the field value for the PN is not X, it must either be a digikey/manufacturer part # or one of the categories in the jellybean parts csv file.
        if (pnFieldIsEmpty(root)):
            sys.exit('Please fix up the PN field for the component')
        # Loop through each component that is in the eeSchema BoM file
        for c in root.find('components').find_all('comp'):
        # If there are any User Created Fields (which would be tagged as fields), see if one of the fields (tagged field) is named 'pn'
        # NOTE: I "hard code" the field to be named pn... this could be more flexible.  However, since I'm doing this for myself, I'm not concerned with making
        # the name of the field that has the manufactuer's part number to be generalized/more robust.
        #

            for field in c.find('fields').find_all('field'):
                # field['name']  -> this equals 'pn'
                name = (field['name'].lower().strip())
                # If a 'pn' User Created Field was found, 
                # check if it points to using a generic manf. part located
                # in the parts_csvFile
                if name == 'pn':
                    pnValue = (c.find('field').string)
                    # If the PN value is X, this component should be ignored from the BoM.  This means
                    # removing the component from the modified BoM XML file. 
                    if pnValue == "X" or pnValue == "x":
                        c.extract()
                        continue
                    # Say for example, the string is 'C'
                    if pnValue in uniqueCategories:
                        # Say for example, the value is .1u
                        value = (c.find('value').string)
                        # Go to the beginning of the csv parts file
                        csvfile.seek(0)
                        csvReader.__init__(csvfile)
                        # Look for the row in the csv parts file that matches the Category and value.
                        # First, use a boolean to figure out if a given PN value is in one of the categories of the JellyBean parts but there is no entry for the ref
                        # value.  e.g.: PN = R (so a Jellybean part) R5=4k7boo (there is no 4k7boo part number in JellyBean parts).
                        didNotFindJellyBeanPart = True
                        for row in csvReader:
                            if row['Category'] == pnValue:
                                if row['Value'] == value:
                                    # Pull out the manufacturer's part number that will replace the Category string (e.g.: "Capacitor")
                                    mfr_pn = row['PN']
                                    # Modify the xml object by replacing the jellybean part reference to a manufactuer's part number
                                    c.fields.field.string = c.fields.field.string.replace(pnValue,mfr_pn)
                                    didNotFindJellyBeanPart = False
                                    break
                        if didNotFindJellyBeanPart:
                            ref = c.get('ref')
                            logger.error('Error! Component '+ref+ ' is a Jellybean part.  The value: ' + value + ' is not in the Jellybean parts csv. Clean up eeSchema...bah bye')
                            sys.exit()
        outputFrom_bom2csv.close()
        #
        # Make sure to tell Beautiful Soup to encode in Unicode.  If not, there is a high likelihood of getting an error similar to this:
        # UnicodeEncodeError: 'ascii' codec can't encode character u'\xa0' in position 29828: ordinal not in range(128)
        # on write.
        modifiedXml = root.prettify('utf-8')
        #
        # BUG: UnicodeEncodeError: 'ascii' codec can't encode character u'\xa0' in position 29828: ordinal not in range(128)
        # on write.
        with open('modified_outputFrom_bom2csv.xml',"w") as modifiedXmlFile:
            modifiedXmlFile.write(modifiedXml)      
    return modifiedXml
#
# All components in the Kicad schematics must have the pn field set with a valid value.
#    
def pnFieldIsEmpty(root):
    # Loop through each component
    pnFieldIsEmpty = False
    for c in root.find('components').find_all('comp'):
        # The whole kahboodle falls apart if the PN field of a component is not filled in with either a generic component name from the jellybean parts csv or a
        # digikey/manufacturer part number.  If one wasn't entered in eeschema, the name field won't exist within the bom2csv xml.  If that is the case...error...
        if (c.find(attrs={"name":"PN"}) == None):
            logstr = 'Check if there is a value for the PN of component {}.'.format(c['ref'])
            logger.error(logstr)
            pnFieldIsEmpty = True
    return pnFieldIsEmpty
