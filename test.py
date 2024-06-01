import sys
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
import argparse
import requests_html

### BEGIN STARTUP ###
args = argparse.ArgumentParser()
args.add_argument('id', nargs=1, help='ID of the entry to test')
args.add_argument('--no_skip', action='store_true', help='Do not use URL skip')
args = args.parse_args()

config = yaml.load(open('config.yaml', 'r'), Loader=Loader)

session = requests_html.HTMLSession()
### END STARTUP ###

if args.id[0] not in config.keys():
    print(f"Entry {args.id[0]} not found in config file.", file=sys.stderr)
    print(f"Available entries:", file=sys.stderr)
    for key in sorted(config.keys()):
        print(f" * {key}", file=sys.stderr)
    exit(1)

entry = config[args.id[0]]
if not args.no_skip and entry['saved_urls']:
    url = entry['saved_urls'][-1]
else:
    url = entry['url']
response = session.get(url)
response.html.render()
for key in ('next_page', 'title', 'image', 'text'):
    if response.html.xpath(entry[key]):
        print(f"{key}: {response.html.xpath(entry[key])}")
    else:
        print(f"{key}: <Not Found>")

session.close()
sys.exit(0)