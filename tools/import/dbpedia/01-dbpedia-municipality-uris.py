# 01-dbpedia-municipality-uris.py
"""
 This script fetches the municipalities URIs from DBPedia.
 
 Este script traz as URIs de municípios da DBPedia.
"""

import re
import os
import urllib
import pandas as pd
from frictionless import Package

GEO_FOLDER = '../../../data/auxiliary/geographic'
GEO_FILE = 'municipality.csv'
OUTPUT_FOLDER = '../../../data/auxiliary/geographic'
OUTPUT_FILE = 'municipality.csv'

remove_parenthesis = re.compile(r'[^(,]+')

# read SPARQL queries
with open ('dbpedia-pt.sparql', 'r') as f:
    DBPPT_SPARQL_CSV = urllib.parse.urlencode({'query':f.read()})
with open ('dbpedia.sparql', 'r') as f:
    DBP_SPARQL_CSV = urllib.parse.urlencode({'query':f.read()})
DBPEDIA_PT_URL = f'http://pt.dbpedia.org/sparql?default-graph-uri=&{DBPPT_SPARQL_CSV}&should-sponge=&format=text%2Fcsv&timeout=0&debug=on'
DBPEDIA_URL = f'http://dbpedia.org/sparql?default-graph-uri=http%3A%2F%2Fdbpedia.org&{DBP_SPARQL_CSV}&format=text%2Fcsv&CXML_redir_for_subjs=121&CXML_redir_for_hrefs=&timeout=30000&debug=on&run=+Run+Query+'

# read data frame from Portuguese DBPedia
dbp_pt = pd.read_csv(DBPEDIA_PT_URL)

# remove parenthesis in city names
dbp_pt['name'] = dbp_pt.name.apply(
    lambda s: remove_parenthesis.match(s).group().strip()
)

# get the state (UF) abbreviations as the DBPedia data does not contain them
package = Package(os.path.join(GEO_FOLDER,'datapackage.json'))
uf = package.get_resource('uf').to_pandas()

# adjust column names and types
uf.rename(columns={'name': 'state'}, inplace=True)
uf.drop('code', axis=1, inplace=True)
uf['state'] = uf['state'].astype('category')

# handle the different types of URIs – main DBPedia or pt DBPedia
dbp_pt['URI_type'] = dbp_pt.city.apply(
    lambda s: 'dbpedia' \
        if s.startswith('http://dbpedia.org/') \
        else 'dbpedia_pt' \
            if s.startswith('http://pt.dbpedia.org/') \
                else None
)

# format the dataframe like the municipality table
dbp_pt = dbp_pt.merge(uf)
dbp_pt.drop('state', axis=1, inplace=True)
dbp_pt.rename(columns={'abbr': 'uf'}, inplace=True)
dbp_pt.rename(columns={'city': 'URI'}, inplace=True)
dbp_pt = dbp_pt.loc[:, ['name', 'uf', 'URI', 'URI_type']] # discard all other columns
dbp_pt.sort_values(by=['uf', 'name', 'URI'], inplace=True)
dbp_pt.drop_duplicates(subset=['name', 'uf', 'URI_type'], keep='first', inplace=True)

# create dbpedia and dbpedia_pt columns depending on the value of URI
dbp_pt = (
    dbp_pt
    .merge(
        (
            dbp_pt
            .pivot(index=['name', 'uf'], columns='URI_type', values='URI')
            .reindex()
        ), on=['name', 'uf'], how='left'
    )
    .drop(['URI', 'URI_type'], axis=1)
    .drop_duplicates()
)

# get the municipality codes as the DBPedia data does not contain them
mun = package.get_resource('municipality').to_pandas()

# just add the municipality codes to the dataframe
dbp_pt = dbp_pt.merge( 
    mun.loc[:, ['code', 'name', 'uf']], # use just those columns for merge
    on=['name', 'uf'], # keys for the join operation
    how='right', # keep the keys from mun dataframe even if not found on dbp_pt
).reindex(columns=['code', 'name', 'uf', 'dbpedia', 'dbpedia_pt'])

# sort both dataframes to align them
assert len(dbp_pt) == len(mun) # must be the same size
dbp_pt.sort_values(by='code', inplace=True)
mun.sort_values(by='code', inplace=True)
dbp_pt.set_index(dbp_pt.code, inplace=True) # make the index be the code
mun.set_index(mun.code, inplace=True) # make the index be the code

# update the URIs, if present. Otherwise, preserve the old ones
mun['dbpedia'] = (
    mun['dbpedia'].combine(
        dbp_pt['dbpedia'],
        lambda old_URI, new_URI: old_URI if new_URI is None else new_URI
    ) if 'dbpedia' in mun.columns \
    else dbp_pt['dbpedia']
)
mun['dbpedia_pt'] = (
    mun['dbpedia_pt'].combine(
        dbp_pt['dbpedia_pt'],
        lambda old_URI, new_URI: old_URI if new_URI is None else new_URI
    ) if 'dbpedia_pt' in mun.columns \
    else dbp_pt['dbpedia_pt']
)

# write back the csv
mun.to_csv(os.path.join(OUTPUT_FOLDER, OUTPUT_FILE), index=False)

