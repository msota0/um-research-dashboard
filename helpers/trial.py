# import dimcli, os
# from dotenv import load_dotenv
# load_dotenv()
# dimcli.login(key=os.getenv('DIMENSIONS_API_KEY'), endpoint='https://app.dimensions.ai/api/dsl/v2')
# dsl = dimcli.Dsl()
# res = dsl.query('''search organizations where name = \"University of Mississippi\" return organizations[id+name+city_name+country_name] limit 10''')
# for r in res.json.get('organizations', []):
#     print(r)

# from backend.api.cache import CacheManager
# import os
# from dotenv import load_dotenv
# load_dotenv()
# c = CacheManager(os.getenv('CACHE_DB_PATH', 'cache.db'))
# for key in [
#     'dimensions:pubs_by_year:grid.266226.6',
#     'dimensions:publications:grid.266226.6',
#     'dimensions:grants:grid.266226.6',
#     'dimensions:researchers:grid.266226.6',
#     'dimensions:clinical_trials:grid.266226.6',
#     'dimensions:patents:grid.266226.6',
#     'dimensions:collab_orgs:grid.266226.6',
# ]:
#     c.invalidate(key)
# print('Cache cleared')

# from dotenv import load_dotenv; load_dotenv()
# from backend.api.cache import CacheManager
# from backend.api.openalex import OpenAlexClient
# from backend.api.dimensions import DimensionsClient
# import os, time, logging
# logging.basicConfig(level=logging.INFO)
# import os
# cache = CacheManager(os.getenv('CACHE_DB_PATH', 'cache.db'))
# oa = OpenAlexClient(os.getenv('OPENALEX_EMAIL', 'research@olemiss.edu'), cache)
# dim = DimensionsClient(os.getenv('DIMENSIONS_API_KEY', ''), cache)
# authors = oa.get_top_authors(page=1, per_page=10).get('items', [])
# for a in authors[:3]:
#     print(f'Testing {a[\"name\"]}...')
#     dois = oa.get_author_dois(a['id'])[:10]
#     print(f'  {len(dois)} DOIs, first: {dois[0] if dois else None}')
#     sources = dim.get_author_citation_sources(a['id'], dois)
#     print(f'  Sources found: {len(sources)}')


# """
# trial.py — Test different Dimensions DSL approaches to find what works.
# Run: python trial.py
# """
# import dimcli
# import os
# from dotenv import load_dotenv

# load_dotenv()
# API_KEY = os.getenv("DIMENSIONS_API_KEY")

# dimcli.login(key=API_KEY, endpoint="https://app.dimensions.ai/api/dsl/v2")
# dsl = dimcli.Dsl()

# # Test DOIs from Paul M. Thompson (a known UM Oxford author)
# test_doi_bare   = "10.1073/pnas.0402680101"
# test_doi_full   = "https://doi.org/10.1073/pnas.0402680101"

# print("=" * 60)
# print("TEST 1: doi in [] with bare DOI")
# res = dsl.query(f'search publications where doi in ["{test_doi_bare}"] return publications[id+doi+journal] limit 5')
# print(f"  Results: {res.json.get('_stats', {})}")
# print(f"  Pubs: {len(res.json.get('publications', []))}")

# print()
# print("TEST 2: doi in [] with full URL")
# res = dsl.query(f'search publications where doi in ["{test_doi_full}"] return publications[id+doi+journal] limit 5')
# print(f"  Results: {res.json.get('_stats', {})}")
# print(f"  Pubs: {len(res.json.get('publications', []))}")

# print()
# print("TEST 3: doi = single bare DOI")
# res = dsl.query(f'search publications where doi = "{test_doi_bare}" return publications[id+doi+journal+open_access+publisher] limit 5')
# print(f"  Results: {res.json.get('_stats', {})}")
# pubs = res.json.get('publications', [])
# print(f"  Pubs: {len(pubs)}")
# if pubs:
#     print(f"  Sample: {pubs[0]}")

# print()
# print("TEST 4: doi = full URL DOI")
# res = dsl.query(f'search publications where doi = "{test_doi_full}" return publications[id+doi+journal+open_access+publisher] limit 5')
# print(f"  Results: {res.json.get('_stats', {})}")
# pubs = res.json.get('publications', [])
# print(f"  Pubs: {len(pubs)}")
# if pubs:
#     print(f"  Sample: {pubs[0]}")

# print()
# print("TEST 5: query UM Oxford publications and check what journal/OA looks like")
# res = dsl.query(f'search publications where research_orgs = "grid.251313.7" return publications[id+doi+journal+open_access+publisher] limit 3')
# pubs = res.json.get('publications', [])
# print(f"  Pubs: {len(pubs)}")
# for p in pubs:
#     print(f"  - doi: {p.get('doi')}")
#     print(f"    journal: {p.get('journal')}")
#     print(f"    open_access: {p.get('open_access')}")
#     print(f"    publisher: {p.get('publisher')}")

# print()
# print("TEST 6: search by researcher name from UM")
# res = dsl.query('search publications where research_orgs = "grid.251313.7" return researchers[id+first_name+last_name+orcid_id] limit 5')
# researchers = res.json.get('researchers', [])
# print(f"  Researchers: {len(researchers)}")
# for r in researchers:
#     print(f"  - {r.get('first_name')} {r.get('last_name')} id={r.get('id')}")

# print()
# if researchers:
#     rid = researchers[0].get('id')
#     rname = f"{researchers[0].get('first_name')} {researchers[0].get('last_name')}"
#     print(f"TEST 7: query publications by researcher id ({rname})")
#     res = dsl.query(f'search publications where researchers.id = "{rid}" return publications[id+doi+journal+open_access+publisher] limit 5')
#     pubs = res.json.get('publications', [])
#     print(f"  Pubs: {len(pubs)}")
#     for p in pubs[:2]:
#         print(f"  - doi: {p.get('doi')}")
#         print(f"    journal: {p.get('journal')}")
#         print(f"    open_access: {p.get('open_access')}")

# """
# trial.py — Test citation sources with the fixed implementation.
# Run: python trial.py
# """
# import dimcli
# import os
# import logging
# from dotenv import load_dotenv

# load_dotenv()
# logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# from backend.api.cache import CacheManager
# from backend.api.openalex import OpenAlexClient
# from backend.api.dimensions import DimensionsClient

# cache = CacheManager(os.getenv("CACHE_DB_PATH", "cache.db"))
# oa    = OpenAlexClient(os.getenv("OPENALEX_EMAIL", "research@olemiss.edu"), cache)
# dim   = DimensionsClient(os.getenv("DIMENSIONS_API_KEY", ""), cache)

# # Get top 5 authors
# print("Fetching top authors...")
# authors_data = oa.get_top_authors(page=1, per_page=25)
# authors = authors_data.get("items", [])[:5]

# for author in authors:
#     aid  = author["id"]
#     name = author["name"]
#     orcid = author.get("orcid", "")
#     print(f"\n{'='*60}")
#     print(f"Author: {name}")
#     print(f"  OpenAlex ID: {aid}")
#     print(f"  ORCID: {orcid}")

#     # Test researcher ID lookup
#     dim_rid = dim._find_dimensions_researcher_id(aid)
#     print(f"  Dimensions researcher ID: {dim_rid or '(not found)'}")

#     # Clear cached result to force fresh fetch
#     cache.invalidate(f"dimensions:citation_sources:{aid}")

#     # Get DOIs
#     dois = oa.get_author_dois(aid)
#     print(f"  DOIs: {len(dois)} (first: {dois[0] if dois else None})")

#     # Get citation sources
#     sources = dim.get_author_citation_sources(aid, dois[:20])  # limit to 20 DOIs for test
#     print(f"  Citation sources found: {len(sources)}")
#     for s in sources[:5]:
#         print(f"    - {s['source_name']} | {s['citation_count']} citations | OA: {s['oa_type']}")

# """
# trial.py — Test outgoing citation sources (what authors cite, not who cites them).
# Run: python trial.py
# """
# import os, logging
# from dotenv import load_dotenv

# load_dotenv()
# logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# from backend.api.cache import CacheManager
# from backend.api.openalex import OpenAlexClient
# from backend.api.dimensions import DimensionsClient

# cache = CacheManager(os.getenv("CACHE_DB_PATH", "cache.db"))
# oa    = OpenAlexClient(os.getenv("OPENALEX_EMAIL", "research@olemiss.edu"), cache)
# dim   = DimensionsClient(os.getenv("DIMENSIONS_API_KEY", ""), cache)

# authors_data = oa.get_top_authors(page=1, per_page=25)
# authors = authors_data.get("items", [])[:5]

# for author in authors:
#     aid  = author["id"]
#     name = author["name"]
#     print(f"\n{'='*60}")
#     print(f"Author: {name}  |  OA ID: {aid}")

#     dim_rid = dim._find_dimensions_researcher_id(aid)
#     print(f"Dimensions researcher ID: {dim_rid or '(not matched via ORCID)'}")

#     cache.invalidate(f"dimensions:citation_sources:{aid}")

#     dois = oa.get_author_dois(aid)
#     print(f"DOIs available: {len(dois)}")

#     sources = dim.get_author_citation_sources(aid, dois)
#     print(f"Unique sources cited: {len(sources)}")
#     print("Top 5 sources:")
#     for s in sources[:5]:
#         print(f"  [{s['citation_count']:4d}x]  {s['source_name']}")
#         print(f"           publisher: {s['publisher'] or chr(8212)}")
#         print(f"           OA: {s['oa_type']}  is_oa={s['is_oa']}")

"""
clear_cache.py — Clear authors and citation sources from cache.db
Run: python clear_cache.py
"""
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

db_path = os.getenv("CACHE_DB_PATH", "cache.db")
conn = sqlite3.connect(db_path)

deleted_authors = conn.execute("DELETE FROM cache WHERE key LIKE '%top_authors%'").rowcount
deleted_citations = conn.execute("DELETE FROM cache WHERE key LIKE '%citation_sources%'").rowcount
conn.commit()
conn.close()

print(f"Cleared {deleted_authors} top_authors entries")
print(f"Cleared {deleted_citations} citation_sources entries")
print("Done — run python seed.py to re-seed")