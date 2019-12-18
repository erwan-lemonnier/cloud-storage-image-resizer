import sys
import logging
from cloudstorageimageresizer import ImageResizer
from google.cloud import storage

# Demonstrate module usage and asserts its behavior (I know, this is not a
# proper test suite...)
#
# Requirements:
# 1. Set the environment variables AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
# 2. Set S3_REGION and BUCKET_NAME to whatever fits you
#
# Run:
# python example.py

BUCKET_NAME = 'gfdusrpcts'

# Logging setup
log = logging.getLogger(__name__)
root = logging.getLogger()
root.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s: %(levelname)s %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)
logging.getLogger('boto').setLevel(logging.INFO)
# EOF logging setup. Pfew.

client = storage.Client.from_service_account_json('gcloud-credentials.json')

i = ImageResizer(client)

i.fetch_image_from_url('https://cdn.shopify.com/s/files/1/1414/7912/products/olm_50macs_rainbow.jpg?v=1541103852')

url = i.store(
    in_bucket=BUCKET_NAME,
    key_name='raw.png'
)
log.info("Got url %s" % url)

want = 'https://storage.googleapis.com/%s/%s' % (BUCKET_NAME, 'raw.png')
assert url == want, '%s == %s' % (url, want)

# apply exif orientation, if any
i.orientate()

# resize to width 200
ii = i.resize(width=200)
url_w200 = ii.store(
    in_bucket=BUCKET_NAME,
    key_name='raw_w200.png'
)
log.info("Got url %s" % url_w200)

want = 'https://storage.googleapis.com/%s/%s' % (BUCKET_NAME, 'raw_w200.png')
assert url_w200 == want, '%s == %s' % (url_w200, want)

# resize to height 200
ii = i.resize(height=200)
url_h200 = ii.store(
    in_bucket=BUCKET_NAME,
    key_name='raw_h200.png'
)
log.info("Got url %s" % url_h200)

# resize to a 100 square
ii = i.resize(width=100, height=100)
url_w100_h100 = ii.store(
    in_bucket=BUCKET_NAME,
    key_name='raw_w100_h100.png'
)
log.info("Got url %s" % url_w100_h100)
