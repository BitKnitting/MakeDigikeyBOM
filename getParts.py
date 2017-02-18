#
# A HUGE THANK YOU to devbisme for Kicost.
# https://github.com/xesscorp/KiCost
# The majority of the code in this module was copy/pasted from Kicost.
#
from bs4 import BeautifulSoup
import logging
from collections import defaultdict
logger = logging.getLogger(__name__)
SEPRTR = ':'  # Delimiter between library:component, distributor:field, etc.


def getParts(modifiedBOM2csvFile):
        # Get groups of identical parts.  Function comes from Kicost.s
    components_by_part_number = group_components_by_part_number(modifiedBOM2csvFile)
    # Create an HTML page containing all the local part information.
#    local_part_html = create_local_part_html(parts)
    return components_by_part_number
#
# Group parts together that are the same into a component_groups array.  
# Parts are the same when both the reference prefix and the value are the same.  For example, 
# a schematic has 3 resistors - R1, R101, R202 all with the same value of .1u  .  This function will group these three
# into one component_group.  
#
def group_components_by_part_number(bom2csvFile):
    #################################################################
    def extract_part_number(part):
        '''Extract XML fields from the library part.'''
        try:
            for f in part.find('fields').find_all('field'):
                # Remove case of field name along with leading/trailing whitespace.
                name = str(f['name'].lower().strip())
                if (name == 'pn'):
                    # Store the part number
                    part_number = (f.string).strip(' \t\n\r')
        except AttributeError:
            raise
        except Exception:
            # The part number must exist on each component.
            logger.error('There was no part number.',exc_info=True)
            exit   
        return part_number
    #################################################################    
    # Read-in the bom2csv XML file to get a tree and get its root.
    root = BeautifulSoup(bom2csvFile,"lxml")        

    # Go through each component placed on the schematic and put the
    # part number and value fields into a fields dictionary.  Then
    # each component gets put into a components['ref'] entry.  For example.
    # pn = XPEBRD-L1-R250-00601 , value = RED_LED for ref=D1
    # fields['pn'] = 'XPEBRD-L1-R250-00601'
    # fields['value'] = 'RED_LED'
    # components['D1'] = fields
    components = {}
    for c in root.find('components').find_all('comp'):
        # Here is an example component:
        #     <comp ref="D1">
        #       <value>RED_LED</value>
        #       <fields>
        #         <field name="PN">XPEBRD-L1-R250-00601</field>
        #       </fields>
        #       <libsource lib="device" part="LED"/>
        #       <sheetpath names="/" tstamps="/"/>
        #       <tstamp>56D8426F</tstamp>
        #     </comp>  


        # Get the <fields> within the <comp>.  The <fields> tag is used within the Kicad
        # schematic to store user defined fields.  This becomes super important here because 
        # Note the PN <field>  This contains the all important part numnber.
        part_number_and_value = {}
        part_number_and_value['pn'] = extract_part_number(c)
        try:
            part_number_and_value['value'] = str(c.find('value').string).strip(' \t\n\r')
        except:
            logstr = 'Error! PN '+part_number_and_value['pn']+ ' has a non-ascii character in the value field'
            logger.error(logstr) 
            exit
        # Store the fields for the part using the reference identifier as the key.
        components[str(c['ref'])] = part_number_and_value
    # Group components that share the same part number
    # First, get the unique part numbers
    unique_part_numbers = set()
    for ref,part_number_and_value in list(components.items()):
        unique_part_numbers.add(part_number_and_value['pn'])
    # Now group components by their part number.  For example, let's say C1 and C2 have the same part number = 5
    # components_by_part_number['5'] = ['C1', 'C2']
    # I was reading about defaultdict() in this blog post:  https://codefisher.org/catch/blog/2015/04/22/python-how-group-and-count-dictionaries/
    components_by_part_number = defaultdict(list)
    for ref,part_number_and_value in list(components.items()):
        component_info = {}
        component_info['ref'] = ref
        component_info['value'] = part_number_and_value['value']
        components_by_part_number[part_number_and_value['pn']].append(component_info)
    return components_by_part_number
