import logging
import requests
from io import BytesIO
from PIL import Image, ExifTags
from PIL import ImageOps, ImageDraw
from PIL import ImageFilter


log = logging.getLogger(__name__)


class CloudStorageImageResizerException(Exception):
    pass

class InvalidParameterException(CloudStorageImageResizerException):
    pass

class CantFetchImageException(CloudStorageImageResizerException):
    pass

class RTFMException(CloudStorageImageResizerException):
    pass


class ImageResizer(object):

    def __init__(self, client):
        if not client or 'google.cloud.storage.client.Client' not in str(type(client)):
            raise InvalidParameterException("Expecting an instance of boto s3 connection")
        self.client = client
        self.image = None
        self.exif_tags = {}


    def fetch(self, url):
        """Fetch an image and keep it in memory"""
        assert url
        log.debug("Fetching image at url %s" % url)
        res = requests.get(url)
        if res.status_code != 200:
            raise CantFetchImageException("Failed to load image at url %s" % url)
        image = Image.open(BytesIO(res.content))

        # Fetch exif tags (if any)
        if image._getexif():
            tags = dict((ExifTags.TAGS[k].lower(), v) for k, v in list(image._getexif().items()) if k in ExifTags.TAGS)
            self.exif_tags = tags

        # Make sure Pillow does not ignore alpha channels during conversion
        # See http://twigstechtips.blogspot.se/2011/12/python-converting-transparent-areas-in.html
        image = image.convert("RGBA")

        canvas = Image.new('RGBA', image.size, (255, 255, 255, 255))
        canvas.paste(image, mask=image)
        self.image = canvas

        return self


    def orientate(self):
        """Apply exif orientation, if any"""

        log.debug("Image has exif tags: %s" % self.exif_tags)

        # No exif orientation?
        if 'orientation' not in self.exif_tags:
            log.info("No exif orientation known for this image")
            return self

        # If image has an exif rotation, apply it to the image prior to resizing
        # See http://stackoverflow.com/questions/4228530/pil-thumbnail-is-rotating-my-image

        angle = self.exif_tags['orientation']
        log.info("Applying exif orientation %s to image" % angle)
        angle_to_degrees = [
            # orientation = transformation
            lambda i: i,
            lambda i: i.transpose(Image.FLIP_LEFT_RIGHT),
            lambda i: i.transpose(Image.ROTATE_180),
            lambda i: i.transpose(Image.FLIP_TOP_BOTTOM),
            lambda i: i.transpose(Image.ROTATE_90).transpose(Image.FLIP_LEFT_RIGHT),
            lambda i: i.transpose(Image.ROTATE_270),
            lambda i: i.transpose(Image.ROTATE_90).transpose(Image.FLIP_TOP_BOTTOM),
            lambda i: i.transpose(Image.ROTATE_90),
        ]

        assert angle >= 1 and angle <= 8
        f = angle_to_degrees[angle - 1]
        self.image = f(self.image)
        return self


    def resize(self, width=None, height=None):
        """Resize the in-memory image previously fetched, and
        return a clone of self holding the resized image"""
        if not width and not height:
            raise InvalidParameterException("One of width or height must be specified")
        if not self.image:
            raise RTFMException("No image loaded! You must call fetch() before resize()")

        cur_width = self.image.width
        cur_height = self.image.height

        if width and height:
            to_width = width
            to_height = height
        elif width:
            to_width = width
            to_height = int(cur_height * width / cur_width)
        elif height:
            to_width = int(cur_width * height / cur_height)
            to_height = height

        # Return a clone of self, loaded with the resized image
        clone = ImageResizer(self.client)
        log.info("Resizing image from (%s, %s) to (%s, %s)" % (cur_width, cur_height, to_width, to_height))
        clone.image = self.image.resize((to_width, to_height), Image.ANTIALIAS)

        return clone


    def crop(self, width=None, height=None):
        """Crop this image to a box, centered on the middle of the image, of size width
        x height pixels. The croped section must be smaller than the current
        image. Both width and height must be set
        """
        assert width is not None
        assert height is not None

        w = self.image.width
        h = self.image.height

        assert w >= width, "Cannot crop to width %s image of smaller width %s" % (width, w)
        assert h >= height, "Cannot crop to height %s image of smaller height %s" % (height, h)

        left = int(w / 2 - width / 2)
        right = int(w / 2 + width / 2)
        upper = int(h / 2 - height / 2)
        lower = int(h / 2 + height / 2)

        log.info("Croping image of size (%s, %s) into a box of size (%s, %s, %s, %s)" % (width, height, left, upper, right, lower))

        clone = ImageResizer(self.client)
        clone.image = self.image.crop((left, upper, right, lower))

        return clone


    def make_round(self):
        """Take a square PNG image and make its corner transparents so it looks like a circle"""
        w = self.image.width
        h = self.image.height

        antialias = 10
        mask = Image.new(
            size=[int(dim * antialias) for dim in self.image.size],
            mode='L',
            color='black',
        )
        draw = ImageDraw.Draw(mask)

        # draw outer shape in white (color) and inner shape in black (transparent)
        edge = 2
        draw.ellipse((edge, edge, w * antialias - edge, h * antialias - edge), fill=255)

        # downsample the mask using PIL.Image.LANCZOS
        # (a high-quality downsampling filter).
        mask = mask.resize(self.image.size, Image.LANCZOS)

        # mask = Image.new('L', (h, w), 0)
        # draw = ImageDraw.Draw(mask)
        # edge = 2
        # draw.ellipse((edge, edge, w - edge, h - edge), fill=255, Image.ANTIALIAS)
        # # mask = mask.filter(ImageFilter.BLUR)
        # # mask = mask.filter(ImageFilter.SMOOTH_MORE)
        # # mask = mask.filter(ImageFilter.SMOOTH_MORE)

        image = ImageOps.fit(self.image, mask.size, centering=(0.5, 0.5))
        image.putalpha(mask)

        clone = ImageResizer(self.client)
        clone.image = image

        return clone


    def store(self, in_bucket=None, key_name=None, metadata=None, quality=95, public=True):
        """Store the loaded image into the given bucket with the given key name. Tag
        it with metadata if provided. Make the Image public and return its url"""
        if not in_bucket:
            raise InvalidParameterException("No in_bucket specified")
        if not key_name:
            raise InvalidParameterException("No key_name specified")
        if not self.image:
            raise RTFMException("No image loaded! You must call fetch() before store()")

        if metadata:
            if type(metadata) is not dict:
                raise RTFMException("metadata must be a dict")
        else:
            metadata = {}

        # metadata['Content-Type'] = 'image/jpeg'

        log.info("Storing image into bucket %s/%s" % (in_bucket, key_name))

        # Export image to a string
        sio = BytesIO()
        self.image.save(sio, 'PNG', quality=quality, optimize=True)
        contents = sio.getvalue()
        sio.close()

        # Get the bucket
        bucket = self.client.get_bucket(in_bucket)

        # Create a key containing the image. Make it public
        # https://googleapis.dev/python/storage/latest/blobs.html
        blob = bucket.blob(key_name)
        blob.metadata = metadata
        blob.upload_from_string(
            contents,
            content_type='image/png',
        )

        if public:
            blob.make_public()

        # Return the key's url
        return blob.public_url
