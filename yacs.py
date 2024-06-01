import argparse
import random
import re
import time
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
import os
import sys
import requests_html

### BEGIN STARTUP ###
if not os.path.exists('config.yaml'):
    example = {
        "ExampleEntry": {           # Name of entry
            "url": None,            # URL to begin scraping at
            "next_page": None,      # XPath to next page button
            "title": None,          # XPath to title
            "image": None,          # XPath to image
            "text": None,           # XPath to descriptive text/author commentary
            "saved_urls": [],       # URLs that have already been saved
            "skip": []              # URLs to skip
            }
        }
    yaml.dump(example, open('config.yaml', 'w'), Dumper=Dumper)
    print("Config file not found. Sample config created.", file=sys.stderr)
    sys.exit(1)

config = yaml.load(open('config.yaml', 'r'), Loader=Loader)

args = argparse.ArgumentParser()
args.add_argument('--delay-min', type=float, nargs=1, default=0, help='Minimum delay between requests')
args.add_argument('--delay-max', type=float, nargs=1, default=0, help='Maximum delay between requests')
args.add_argument('--output', nargs=1, default='output', help='Output directory')
args = args.parse_args()

delay_min = max(0.0, args.delay_min[0] if isinstance(args.delay_min, list) else args.delay_min)
delay_max = max(0.0, args.delay_max[0] if isinstance(args.delay_max, list) else args.delay_max)
if delay_min > delay_max:
    delay_min = delay_max

session = requests_html.HTMLSession()
### END STARTUP ###

if args.test:
    if args.test[0] not in config:
        print(f"Entry \"{args.test[0]}\" not found in config file", file=sys.stderr)
        sys.exit(1)
    entry = config[args.test[0]]
    response = session.get(entry['url'])
    response.html.render()
    for key in entry:
        if key == 'url' or entry[key] is None:
            continue
        if response.html.xpath(entry[key]):
            print(f"{key}: {response.html.xpath(entry[key])}")
        else:
            print(f"{key}: <Not Found>")
    sys.exit(0)

for entry in config.keys():
    _flag = True      # Keep operating while this is set. If we have a failure, unset to jump to next entry
    next_page = None  # Placeholder for next page URL
    savepath = os.path.join(args.output, entry)
    if not os.path.exists(savepath):
        os.makedirs(savepath)
    # Determine if we've already saved any files. Start looking from the last saved URL, otherwise use start URL
    url = config[entry]['saved_urls'][-1] if config[entry]['saved_urls'] else config[entry]['url']
    # Determine our counter position based on existing files
    existing_files = [file for file in os.listdir(savepath) if re.match(r'^\d+', file)]
    existing_files = sorted(existing_files, key=lambda x: int(re.match(r'^(\d+)', x).group(1))) if existing_files else None
    if existing_files:
        counter = int(re.match(r'^(\d+)', existing_files[-1]).group(1)) + 1
    else:
        counter = 1
    scheme, _, domain, _ = url.split('/', 3)

    while _flag:
        # Open and render the page
        res = session.get(url)
        res.html.render()

        # Determine next page URL
        try:
            next_page = res.html.xpath(config[entry]['next_page'])[0]
            if not next_page.startswith('http'):
                next_page = f"{scheme}//{domain}{next_page}"
            else:
                next_page = next_page
        except IndexError:
            print(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {entry}: No next page found at {url}", file=sys.stderr)
            _flag = False

        # Skip if URL is in skip list
        if url in config[entry]['skip']:
            print(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {entry}: Skipping {url} (in skip list)")
            if next_page:
                url = next_page
            else:
                _flag = False
            continue

        # Skip if URL has already been saved
        if url in config[entry]['saved_urls']:
            print(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {entry}: Skipping {url} (already saved)")
            if next_page:
                url = next_page
            else:
                _flag = False
            continue

        # Determine title, use url if not found
        try:
            title = res.html.xpath(config[entry]['title'])[0]
        except IndexError:
            title = url

        # Determine image
        image = res.html.xpath(config[entry]['image'])
        if image:
            image = image[0]
        else:
            print(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {entry}: No image found at {url}", file=sys.stderr)
            sys.exit(1)

        # Determine text
        text = '\n'.join([line.strip() for line in res.html.xpath(config[entry]['text'])]) if config[entry]['text'] else None
        
        # Save image
        if image:
            image_res = session.get(image)
            filepath = os.path.join(savepath, f"{counter:05d} - {title}{os.path.splitext(image)[-1]}")
            if os.path.exists(filepath):
                print(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {entry}: File already exists at {filepath}")
                url = next_page
                counter += 1
                continue
            try:
                with open(filepath, 'wb') as f:
                    f.write(image_res.content)
                    print(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {entry}: Saved {filepath} ({len(image_res.content) / 1024:.1f} KiB)")
                    if next_page is None:
                        _flag = False
                        print(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {entry}: No next page found at {url}", file=sys.stderr)
                    else:
                        url = next_page
                    counter += 1
            except Exception as e:
                print(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {entry}: Error saving image at {url}", file=sys.stderr)
                print(e, file=sys.stderr)
                sys.exit(1)

        # Note that url was saved, update config file with status
        config[entry]['saved_urls'].append(url)
        yaml.dump(config, open('config.yaml', 'w'), Dumper=Dumper)
        
        if delay_min and delay_max:
            delay = random.uniform(delay_min, delay_max)
            print(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {entry}: Delaying {delay:.2f} seconds")
            time.sleep(delay)

### BEGIN SHUTDOWN ###
session.close()
yaml.dump(config, open('config.yaml', 'w'), Dumper=Dumper)
sys.exit(0)
### END SHUTDOWN ###