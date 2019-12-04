# cloudstorageimageresizer

A python module to import, rotate, crop and resize pictures into Google Cloud Storage

## DISCLAIMER

THIS IS NOT AN OFFICIAL GOOGLE MODULE.

## Synopsis

Typical usecase: fetch a bunch of image and generate thumbnails of various
sizes for each of them, stored in Cloud Storage for further delivery via a CDN.

```
from cloudstorageimageresizer import ImageResizer

# Initialize an ImageResizer:
i = ImageResizer()

urls = [
    'http://www.gokqsw.com/images/picture/picture-3.jpg',
    'http://www.gokqsw.com/images/picture/picture-4.jpg'
]

for url in urls:

    # Fetch image into memory and store it in original format to a Google Cloud
    # Storage bucket
    i.fetch(url).store(
        in_bucket='my-images',
        key_name='image-original'
    )

    # Apply the image EXIF rotation, if any
    i.orientate()

    # Resize this image, store it into a Google Cloud Storage bucket and return its url
    url1 = i.resize(
        width=200
    ).store(
        in_bucket='my-images',
        key_name='image-w200'
    )

    # Do it again, with a different size
    url2 = i.resize(
        height=400
    ).store(
        in_bucket='my-images',
        key_name='image-h200'
    )
```

## More explanation

For method parameters, see the code (there isn't much of it ;-)

ImageResizer does all image operations in-memory, without writing images to
disk.

ImageResizer uses PIL, has reasonable defaults for downsizing images and
handle images with alpha channels nicely.

All images are stored in png format to preserve transparency.

## Installation

'cloudstorageimageresizer' requires Pillow, which in turn needs external
libraries.  On ubuntu, you would for example need:

```
sudo apt-get install libjpeg8 libjpeg8-dev libopenjpeg-dev
```

Then

```
pip install cloudstorageimageresizer
```

## Testing

Add your json google api credentials in the file 'gcloud-credentials.json',
edit the BUCKET_NAME in example.py and run it:

```
python example.py
```

## Source code

[https://github.com/erwan-lemonnier/cloud-storage-image-resizer](https://github.com/erwan-lemonnier/cloud-storage-image-resizer)

## Author

Erwan Lemonnier<br/>
[github.com/pymacaron](https://github.com/pymacaron)</br>
[github.com/erwan-lemonnier](https://github.com/erwan-lemonnier)<br/>
[www.linkedin.com/in/erwan-lemonnier/](https://www.linkedin.com/in/erwan-lemonnier/)