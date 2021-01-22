import logging
import requests
from io import BytesIO
from PIL import Image, ExifTags
from PIL import ImageOps, ImageDraw


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
    no_image_loaded_msg = "No image loaded!"

    def __init__(self, client, bucket_name=None):
        """Initialize an ImageResizer with a Google Storage Client instance and
        optionaly the name of the Storage bucket in which to store images.

        """
        gcloud_client_str = 'google.cloud.storage.client.Client'
        if not client or gcloud_client_str not in str(type(client)):
            msg = "Expected an instance of google storage Client, got a %s" % \
                  client
            raise InvalidParameterException(msg)
        self.client = client
        self.image = None
        self.exif_tags = {}
        self.bucket_name = bucket_name

    def __set_exif_tags(self, image):
        # Fetch exif tags (if any)
        if image._getexif():
            tags = dict(
                (ExifTags.TAGS[k].lower(), v)
                for k, v in list(image._getexif().items())
                if k in ExifTags.TAGS
            )
            self.exif_tags = tags

    def __load_image(self, image_in_bytes):
        """Instantiate a Pillow image,
        set its exif tags if any and do some pre-processing"""
        image = Image.open(image_in_bytes)
        self.__set_exif_tags(image)
        # Make sure Pillow does not ignore alpha channels during conversion
        # See http://twigstechtips.blogspot.se/2011/12/python-converting-transparent-areas-in.html  # noqa
        image = image.convert("RGBA")

        canvas = Image.new('RGBA', image.size, (255, 255, 255, 255))
        canvas.paste(image, mask=image)
        self.image = canvas
        return self

    def load_image_from_bytes(self, image):
        """Convert bytes into a Pillow image and keep it in memory"""
        assert image
        log.debug("Load file into memory: %s" % image)
        return self.__load_image(image)

    def fetch_image_from_url(self, url):
        """Fetch an image from a url and keep it in memory"""
        assert url
        log.debug("Fetching image at url %s" % url)
        res = requests.get(url)
        if res.status_code != 200:
            msg = "Failed to load image at url %s" % url
            raise CantFetchImageException(msg)
        return self.__load_image(BytesIO(res.content))

    def load_image_from_bytestring(self, bytestring):
        """Convert a bytestring into a Pillow image and keep it in memory"""
        assert bytestring
        return self.__load_image(BytesIO(bytestring))

    def orientate(self):
        """Apply exif orientation, if any"""

        log.debug("Image has exif tags: %s" % self.exif_tags)

        # No exif orientation?
        if 'orientation' not in self.exif_tags:
            log.debug("No exif orientation known for this image")
            return self

        # If image has an exif rotation, apply it to the image prior to resizing  # noqa
        # See http://stackoverflow.com/questions/4228530/pil-thumbnail-is-rotating-my-image  # noqa

        angle = self.exif_tags['orientation']
        log.debug("Applying exif orientation %s to image" % angle)
        tb = Image.FLIP_TOP_BOTTOM
        lr = Image.FLIP_LEFT_RIGHT
        angle_to_degrees = [
            # orientation = transformation
            lambda i: i,
            lambda i: i.transpose(Image.FLIP_LEFT_RIGHT),
            lambda i: i.transpose(Image.ROTATE_180),
            lambda i: i.transpose(tb),
            lambda i: i.transpose(Image.ROTATE_90).transpose(lr),
            lambda i: i.transpose(Image.ROTATE_270),
            lambda i: i.transpose(Image.ROTATE_90).transpose(tb),
            lambda i: i.transpose(Image.ROTATE_90),
        ]

        assert 1 <= angle <= 8
        f = angle_to_degrees[angle - 1]
        self.image = f(self.image)
        return self

    def resize_if_larger_and_keep_ratio(self, width=None, height=None):
        """Resize the in-memory image with kept ratio automatically"""
        if not width and not height:
            msg = "One of width or height must be specified"
            raise InvalidParameterException(msg)
        if not self.image:
            raise RTFMException(self.no_image_loaded_msg)

        cur_width = self.image.width
        cur_height = self.image.height

        if width and height and cur_width > width and cur_height > height:
            log.debug("Resizing image from (%s, %s) to (%s, %s)" %
                      (cur_width, cur_height, width, height))
            self.image.thumbnail((width, height), Image.ANTIALIAS)
        elif width and cur_width > width:
            log.debug("Resizing image width from %s to %s" %
                      (cur_width, width))
            self.image.thumbnail((width, cur_height), Image.ANTIALIAS)
        elif height and cur_height > height:
            log.debug("Resizing image height from %s to %s" %
                      (cur_height, height))
            self.image.thumbnail((cur_width, height), Image.ANTIALIAS)
        return self

    def resize(self, width=None, height=None, progressive=False):
        """Resize the image in-memory and return a clone of
        self holding the resized image"""
        if not width and not height:
            raise InvalidParameterException("Missing width or height")
        if not self.image:
            raise RTFMException(self.no_image_loaded_msg)

        cur_width = self.image.width
        cur_height = self.image.height

        to_width = None
        to_height = None
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
        log.debug("Resizing image from (%s, %s) to (%s, %s)" %
                  (cur_width, cur_height, to_width, to_height))
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

        assert w >= width, "Cannot crop to width %s image of smaller width %s" % (width, w)  # noqa
        assert h >= height, "Cannot crop to height %s image of smaller height %s" % (height, h)  # noqa

        left = int(w / 2 - width / 2)
        right = int(w / 2 + width / 2)
        upper = int(h / 2 - height / 2)
        lower = int(h / 2 + height / 2)

        log.debug("Cropping image of size "
                  "(%s, %s) into a box of size "
                  "(%s, %s, %s, %s)" %
                  (width, height, left, upper, right, lower))

        clone = ImageResizer(self.client)
        clone.image = self.image.crop((left, upper, right, lower))

        return clone

    def make_round(self):
        """Take a square PNG image and make its corner transparent
        so it looks like a circle"""
        w = self.image.width
        h = self.image.height

        antialias = 10
        mask = Image.new(
            size=[int(dim * antialias) for dim in self.image.size],
            mode='L',
            color='black',
        )
        draw = ImageDraw.Draw(mask)

        # draw outer shape in white (color) and
        #  inner shape in black (transparent)
        edge = 2
        xy = (edge, edge, w * antialias - edge, h * antialias - edge)
        draw.ellipse(xy, fill=255)

        # downsample the mask using PIL.Image.LANCZOS
        # (a high-quality downsampling filter).
        mask = mask.resize(self.image.size, Image.LANCZOS)

        # mask = Image.new('L', (h, w), 0)
        # draw = ImageDraw.Draw(mask)
        # edge = 2
        # draw.ellipse((edge, edge, w - edge, h - edge), fill=255, Image.ANTIALIAS)  # noqa
        # # mask = mask.filter(ImageFilter.BLUR)
        # # mask = mask.filter(ImageFilter.SMOOTH_MORE)
        # # mask = mask.filter(ImageFilter.SMOOTH_MORE)

        image = ImageOps.fit(self.image, mask.size, centering=(0.5, 0.5))
        image.putalpha(mask)

        clone = ImageResizer(self.client)
        clone.image = image

        return clone

    def store_and_return_blob(
            self,
            bucket_name=None,
            key_name=None,
            metadata=None,
            quality=95,
            encoding='PNG',
            progressive=True,
    ):
        """Store the image into the given bucket (or defaults to the bucket passed to
        the constructor), with the given key name.
        Tag it with metadata if provided."""

        assert encoding in ('PNG', 'JPEG')

        if not bucket_name and not self.bucket_name:
            raise InvalidParameterException("No bucket_name specified")
        if not key_name:
            raise InvalidParameterException("No key_name specified")
        if not self.image:
            raise RTFMException(self.no_image_loaded_msg)

        bucket_name = bucket_name or self.bucket_name

        if metadata:
            if type(metadata) is not dict:
                raise RTFMException("metadata must be a dict")
        else:
            metadata = {}

        log.debug("Storing image into bucket %s/%s" % (bucket_name, key_name))

        # Export image to a string
        sio = BytesIO()
        if encoding == 'PNG':
            self.image.save(sio, 'PNG', quality=quality, optimize=True)
        elif encoding == 'JPEG':
            log.info("converting to RGB")
            im = self.image.convert("RGB")
            im.save(sio, 'jpeg', quality=quality, optimize=True, progressive=progressive)
        contents = sio.getvalue()
        sio.close()

        # Get the bucket
        bucket = self.client.get_bucket(bucket_name)

        # Create a key containing the image
        # https://googleapis.dev/python/storage/latest/blobs.html

        encoding_to_content_type = {
            'PNG': 'image/png',
            'JPEG': 'image/jpeg',
        }

        blob = bucket.blob(key_name)
        blob.metadata = metadata
        blob.upload_from_string(
            contents,
            content_type=encoding_to_content_type[encoding],
        )

        # Return the blob
        return blob

    def store_and_return_url(
            self,
            in_bucket=None,
            key_name=None,
            metadata=None,
            quality=95,
            public=True,
            encoding='PNG',
            progressive=True,
    ):
        """Store the loaded image into the given bucket with the given key name. Tag it
        with metadata if provided. Optionally make the Image public. Return its
        url.

        """

        blob = self.store_and_return_blob(
            in_bucket,
            key_name,
            metadata,
            quality,
            encoding=encoding,
            progressive=progressive,
        )

        if public:
            blob.make_public()

        # Return the key's url
        return blob.public_url
