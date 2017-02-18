from bs4 import BeautifulSoup
import urllib as URLL
import httplib
import difflib
import re
import csv
from urllib2 import urlopen, Request, URLError

import logging
HTML_RESPONSE_RETRIES = 2 # Num of retries for getting part data web page.
WEB_SCRAPE_EXCEPTIONS = (URLError, httplib.HTTPException)
logger = logging.getLogger(__name__)
can_make_digikey_file = True
#
# The parts variable was created with defaultDict...
# This function returns either:
# True - the MadeDigikeyBOM.csv file was created and contains the part/price info
# False - the file was not created because more work is needed by the user to clean up the original schematic.
#         Info on what needs to be cleaned up is give in logger.error output (see the console)

def makeDigikeyFile(parts,outDir):
    logStr = 'The number of parts to scrape: {}'.format(len(parts))
    logger.info(logStr)
    counter = 0
    # Open the BoM output file for writing.  If there is at least one row of BoM data, the file will be written.  Info messages are printed for those rows that
    # can't be resolved from scraping Digikey.
    fileName = outDir + "MadeDigikeyBOM.csv"    
    with open(fileName,'w') as csvfile:
        csvwriter = csv.writer(csvfile)    
        write_header(csvwriter)
        # Components is an array of components that share the same part number. Sharing the same part number means
        # the value is the same. For example: 
        # part_number = CL21F104ZBCNNNC
        # components = [{'ref': 'C3', 'value': '.1u'}, {'ref': 'C1', 'value': '.1u'}]
        for part_number, components in parts.iteritems():
            counter += 1
            # All values will be the same because they refer to the same part number
            refs = []
            for i in range(len(components)):
                refs.append(components[i]['ref'])
            refStr = ",".join(refs )
            if part_number != 'None':
                logStr = '{} Getting Digikey info for schematic components: {} part number: {} with value: {}'.format(counter,refStr,part_number,components[0]['value'])
            else:
                logStr = '{} Skipping Digikey info for schematic components: {} part number: {} '.format(counter,refStr,part_number)     
            logger.info(logStr)
            #
            # Scrape Digikey web pages based on the part number to
            # get columns of the spreadsheet.
            # NOTE: I use 'None' as the part number to exclude components with this part from a digikey scrape.
            if (part_number != 'None'):    
                url, digikey_price_number,price_tiers, qty_avail = scrape_part(part_number)
                if can_make_digikey_file:
                    write_row(csvwriter,part_number,components,url,digikey_price_number,price_tiers,qty_avail)  
    return can_make_digikey_file 
def scrape_part(part_number):
    html_tree,url = get_digikey_part_html_tree(part_number) 
    if can_make_digikey_file:
        price_tiers = get_digikey_price_tiers(html_tree)
        qty_avail = get_digikey_qty_avail(html_tree)
        digikey_part_number = get_digikey_part_num(html_tree)
        return url,digikey_part_number,price_tiers,qty_avail 
    else:
        return '','','',''
#def write_row(part_number,refs,url,digikey_price_number,price_tiers,qty_avail):  

def get_digikey_part_html_tree(part_number,url=None,descend=2):
    '''Find the Digikey HTML page for a part number and return the URL and parse tree.'''
    def merge_price_tiers(main_tree, alt_tree):
        '''Merge the price tiers from the alternate-packaging tree into the main tree.'''
        try:
            insertion_point = main_tree.find('table', id='product-dollars').find('tr')
            for tr in alt_tree.find('table', id='product-dollars').find_all('tr'):
                insertion_point.insert_after(tr)
        except AttributeError:
            pass

    def merge_qty_avail(main_tree, alt_tree):
        '''Merge the quantities from the alternate-packaging tree into the main tree.'''
        try:
            main_qty = get_digikey_qty_avail(main_tree)
            alt_qty = get_digikey_qty_avail(alt_tree)
            if main_qty is None:
                merged_qty = alt_qty
            elif alt_qty is None:
                merged_qty = main_qty
            else:
                merged_qty = max(main_qty, alt_qty)
            if merged_qty is not None:
                insertion_point = main_tree.find('td', id='quantityAvailable')
                insertion_point.string = 'Digi-Key Stock: {}'.format(merged_qty)
        except AttributeError:
            pass

 
    # Use the part number to lookup the part using the site search function, unless a starting url was given.
    if url is None:
        url = 'http://www.digikey.com/scripts/DkSearch/dksus.dll?WT.z_header=search_go&lang=en&keywords=' + URLL.quote(
            part_number,
            safe='')
        #url = 'http://www.digikey.com/product-search/en?KeyWords=' + urlquote(pn,safe='') + '&WT.z_header=search_go'
    elif url[0] == '/':
        url = 'http://www.digikey.com' + url

    # Open the URL, read the HTML from it, and parse it into a tree structure.
    req = FakeBrowser(url)
    for _ in range(HTML_RESPONSE_RETRIES):
        try:
            response = urlopen(req)
            html = response.read()
            break
        except WEB_SCRAPE_EXCEPTIONS:
            pass
    else: # Couldn't read the page.
        raise PartHtmlError
    tree = BeautifulSoup(html, 'lxml')

    # If the tree contains the tag for a product page, then return it.
    if tree.find('div', class_='product-top-section') is not None:

        # Digikey separates cut-tape and reel packaging, so we need to examine more pages
        # to get all the pricing info. But don't descend any further if limit has been reached.
        if descend > 0:
            try:
                # Find all the URLs to alternate-packaging pages for this part.
                ap_urls = [
                    ap.find('td',
                            class_='lnkAltPack').a['href']
                    for ap in tree.find(
                        'table',
                        class_='product-details-alternate-packaging').find_all(
                            'tr',
                            class_='more-expander-item')
                ]
                ap_trees_and_urls = [get_digikey_part_html_tree(part_number, ap_url,
                                                                descend=0)
                                     for ap_url in ap_urls]

                # Put the main tree on the list as well and then look through
                # the entire list for one that's non-reeled. Use this as the
                # main page for the part.
                ap_trees_and_urls.append((tree, url))
                if digikey_part_is_reeled(tree):
                    for ap_tree, ap_url in ap_trees_and_urls:
                        if not digikey_part_is_reeled(ap_tree):
                            # Found a non-reeled part, so use it as the main page.
                            tree = ap_tree
                            url = ap_url
                            break  # Done looking.

                # Now go through the other pages, merging their pricing and quantity
                # info into the main page.
                for ap_tree, ap_url in ap_trees_and_urls:
                    if ap_tree is tree:
                        continue  # Skip examining the main tree. It already contains its info.
                    try:
                        # Merge the pricing info from that into the main parse tree to make
                        # a single, unified set of price tiers...
                        merge_price_tiers(tree, ap_tree)
                        # and merge available quantity, using the maximum found.
                        merge_qty_avail(tree, ap_tree)
                    except AttributeError:
                        continue
            except AttributeError:
                pass
        return tree, url  # Return the parse tree and the URL where it came from.

    # If the tree is for a list of products, then examine the links to try to find the part number.
    if tree.find('table', id='productTable') is not None:
        if descend <= 0:
            raise PartHtmlError
        else:
            # Look for the table of products.
            products = tree.find(
                'table',
                id='productTable').find('tbody').find_all('tr')

            # Extract the product links for the part numbers from the table.
            # Extract links for both manufacturer and catalog numbers.
            product_links = [p.find('td',
                                    class_='tr-mfgPartNumber').a
                             for p in products]
            product_links.extend([p.find('td',
                                    class_='tr-dkPartNumber').a
                             for p in products])

            # Extract all the part numbers from the text portion of the links.
            part_numbers = [l.text for l in product_links]

            # Look for the part number in the list that most closely matches the requested part number.
            match = difflib.get_close_matches(part_number, part_numbers, 1, 0.0)[0]

            # Now look for the link that goes with the closest matching part number.
            for l in product_links:
                if l.text == match:
                    # Get the tree for the linked-to page and return that.
                    return get_digikey_part_html_tree(part_number,
                                                      url=l['href'],
                                                      descend=descend - 1)

    # If the HTML contains a list of part categories, then give up.
    if tree.find('form', id='keywordSearchForm') is not None:
        logger.error('The part {} cannot be found on Digikey'.format(part_number))
        global can_make_digikey_file
        can_make_digikey_file = False
        return ' ',' '

    # I don't know what happened here, so give up.
    raise PartHtmlError
#
# 
def get_digikey_qty_avail(html_tree):
    '''Get the available quantity of the part from the Digikey product page.'''
    try:
        qty_str = html_tree.find('td', id='quantityAvailable').text
    except AttributeError:
        # No quantity found (not even 0) so this is probably a non-stocked part.
        # Return None so the part won't show in the spreadsheet for this dist.
        return None
    try:
        qty_str = re.search('(stock:\s*)([0-9,]*)', qty_str,
                            re.IGNORECASE).group(2)
        return int(re.sub('[^0-9]', '', qty_str))
    except (AttributeError, ValueError):
        # No quantity found (not even 0) so this is probably a non-stocked part.
        # Return None so the part won't show in the spreadsheet for this dist.
        return None
def digikey_part_is_reeled(html_tree):
    '''Returns True if this Digi-Key part is reeled or Digi-reeled.'''
    qty_tiers = list(get_digikey_price_tiers(html_tree).keys())
    if len(qty_tiers) > 0 and min(qty_tiers) >= 100:
        return True
    if html_tree.find('table',
                      id='product-details-reel-pricing') is not None:
        return True
    return False
def get_digikey_price_tiers(html_tree):
    '''Get the pricing tiers from the parsed tree of the Digikey product page.'''
    price_tiers = {}
    try:
        for tr in html_tree.find('table', id='product-dollars').find_all('tr'):
            try:
                td = tr.find_all('td')
                qty = int(re.sub('[^0-9]', '', td[0].text))
                price_tiers[qty] = float(re.sub('[^0-9\.]', '', td[1].text))
            except (TypeError, AttributeError, ValueError,
                    IndexError):  # Happens when there's no <td> in table row.
                continue
    except AttributeError:
        # This happens when no pricing info is found in the tree.
        return price_tiers  # Return empty price tiers.
    return price_tiers
def get_digikey_part_num(html_tree):
    '''Get the part number from the Digikey product page.'''
    try:
        return re.sub('\s', '', html_tree.find('td',
                                               id='reportPartNumber').text)
    except AttributeError:
        return ''

def FakeBrowser(url):
    req = Request(url)
    req.add_header('Accept-Language', 'en-US')
    req.add_header('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_0) AppleWebKit/536.3 (KHTML, like Gecko) Chrome/19.0.1063.0 Safari/536.3')
    return req
class PartHtmlError(Exception):
    '''Exception for failed retrieval of an HTML parse tree for a part.'''
    pass        



def write_header(csvwriter):
    csvwriter.writerow(('Reference','Value','Quantity','Manf Part #','Digikey Part #','1','10','100','1000','Qty Avail','Link'))
 
def write_row(csvwriter,part_number,components,url,digikey_part_number,price_tiers,qty_avail):
    refs = []
    numComponents = len(components)
    for i in range(numComponents):
        refs.append(components[i]['ref'])
    refStr = ",".join(refs )
    # all value fields are the same
    value = components[0]['value']
    price_1 = price_tiers.get(1,0)
    price_10 = price_tiers.get(10,0) 
    price_10 = price_10 if price_10 > 0 else price_1
    price_100 = price_tiers.get(100,0)
    price_100 = price_100 if price_100 > 0 else price_10
    price_1000 = price_tiers.get(1000,0)
    price_1000 = price_1000 if price_1000 > 0 else price_100
    csvwriter.writerow((refStr,value,numComponents,part_number,digikey_part_number,price_1,price_10,price_100,price_1000,qty_avail,url))