# import dimcli, os
# from dotenv import load_dotenv
# load_dotenv()
# dimcli.login(key=os.getenv('DIMENSIONS_API_KEY'), endpoint='https://app.dimensions.ai/api/dsl/v2')
# dsl = dimcli.Dsl()
# res = dsl.query('''search organizations where name = \"University of Mississippi\" return organizations[id+name+city_name+country_name] limit 10''')
# for r in res.json.get('organizations', []):
#     print(r)

from api.cache import CacheManager
import os
from dotenv import load_dotenv
load_dotenv()
c = CacheManager(os.getenv('CACHE_DB_PATH', 'cache.db'))
for key in [
    'dimensions:pubs_by_year:grid.266226.6',
    'dimensions:publications:grid.266226.6',
    'dimensions:grants:grid.266226.6',
    'dimensions:researchers:grid.266226.6',
    'dimensions:clinical_trials:grid.266226.6',
    'dimensions:patents:grid.266226.6',
    'dimensions:collab_orgs:grid.266226.6',
]:
    c.invalidate(key)
print('Cache cleared')