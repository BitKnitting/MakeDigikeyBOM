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
    # Read the list of "jellybean" manufacturers parts csv file.
    # Since this code is not robust, I assume the csv file has three columns named
    # Category,Value,MFR_PN
    # After this header row, entries would look like (for example):
    
    # Create a set that contains the unique category name.  For example,
    # CAPACITOR is a category name for multiple entries in the parts_csvFile - 1u, .1u, etc.
    uniqueCategories = set()
    with jellyBeanFile as csvfile:
        csvReader = csv.DictReader(csvfile)
        for row in csvReader:
            uniqueCategories.add(row['Category'])
        # Read the BoM file created within eeSchema into Beautiful Soup
        # I noticed the kicost code used the lxml parser.  This wasn't installed on my Mac.  I saw it discussed in the Beautiful Soup documentation:
        # http://www.crummy.com/software/BeautifulSoup/bs4/doc/  (see Installing a parser).
        # I ran easy_install lxml and was treated to - Could not find function xmlCheckVersion in library libxml2. Is libxml2 installed?
        # Perhaps try: xcode-select --install ... which I guess installs XCode command line utilities?  Once I installed, the lxml parser compiled/built/installed...
        # I don't thoroughly understand the install process but it worked.... so...I continue.  More details on error installing lxml on Mac OSX is discussed:
        # http://stackoverflow.com/questions/19548011/cannot-install-lxml-on-mac-os-x-10-9
        root = BeautifulSoup(outputFrom_bom2csv,"lxml")
        # All components must have a <field> named pn with at least one character for the pn part name (called 'category' below)
        if (pnFieldsNeedWork(root,uniqueCategories)):
            sys.exit('Please fix up the PN fields within the Schematic(s)')
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
                    category = (c.find('field').string)
                    # Say for example, the string is 'C'
                    if category in uniqueCategories:
                        # Say for example, the value is .1u
                        value = (c.find('value').string)
                        # Go to the beginning of the csv parts file
                        csvfile.seek(0)
                        csvReader.__init__(csvfile)
                        # Look for the row in the csv parts file that matches the Category and value.
                        for row in csvReader:
                            if row['Category'] == category:
                                if row['Value'] == value:
                                    # Pull out the manufacturer's part number that will replace the Category string (e.g.: "Capacitor")
                                    mfr_pn = row['MFR_PN']
                                    # Modify the xml object by replacing the jellybean part reference to a manufactuer's part number
                                    c.fields.field.string = c.fields.field.string.replace(category,mfr_pn)
                                    break
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
def pnFieldsNeedWork(root,uniqueCategories):
    # Loop through each component
    pnFieldNeedsWork = False
    for c in root.find('components').find_all('comp'):
        # Check to see if there is a pn <field> tag
        if (c.find(attrs={"name":"PN"}) == None):
            logstr = 'Check the PN field of component {}.'.format(c['ref'])
            logger.error(logstr)
            pnFieldNeedsWork = True
        else:
            c.find(attrs={"name":"PN"})
            if (len(c.find('field').string) <= 0):
                logstr = 'Check the PN field of component {}.'.format(c['ref'])
                logger.error(logstr)
                pnFieldNeedsWork = True

    return pnFieldNeedsWork
