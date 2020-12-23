import argparse
import json
import re
import os
import requests
import pandas as pd
import xml.etree.ElementTree as et
import time
from PIL import Image

def parse_json(json_file):
    data_dict = json.load(json_file)
    return pd.json_normalize(data_dict['slides'])


def get_video_id(video_url):
    ids = re.findall('https://slideslive\\.(com|de)/([0-9]*)/([^/]*)(.*)', video_url)
    if len(ids) < 1:
        print('Error: {0} is not a correct url.'.format(video_url))
        exit()
    return ids[0][1], ids[0][2]


def download_save_file(url, save_path, headers, wait_time=0.2):
    r = requests.get(url, headers=headers)
    with open(save_path, 'wb') as f:
        f.write(r.content)
    time.sleep(wait_time)


def download_slides_json(base_url, video_id, video_name, headers, wait_time):
    # Example: https://d2ygwrecguqg66.cloudfront.net/data/presentations/38943570/v3/slides.json
    folder_name = '{0}-{1}'.format(video_id, video_name)
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)

    image_folder_name = os.path.join(folder_name, 'images')
    if not os.path.exists(image_folder_name):
        os.mkdir(image_folder_name)

    if os.path.isfile(folder_name):
        print('Error: {0} is a file, can\'t create a folder with that name'.format(folder_name))
        exit()

    file_path = '{0}/{1}.json'.format(folder_name, video_id)
    if not os.path.exists(file_path):
        json_url = os.path.join(base_url, video_id, 'v3', 'slides.json')
        print('downloading {}'.format(file_path))
        download_save_file(json_url, file_path, headers, wait_time)

    return open(file_path, 'r')


def get_image_file_path(folder_name, time, image_name, size):
    time_str = f'{int(time):08d}'
    return f'{folder_name}/images/{time_str}-{image_name}-{size}.jpg'


def download_slides(video_id, video_name, df, base_img_url, size, headers, wait_time):
    folder_name = '{0}-{1}'.format(video_id, video_name)
    for index, row in df.iterrows():
        image_name = row['image.name']
        img_url = base_img_url.format(video_id, image_name, size)
        file_path = get_image_file_path(folder_name, row['time'], image_name, size)
        print('downloading {}'.format(file_path))
        download_save_file(img_url, file_path, headers, wait_time)


def create_ffmpeg_concat_file(video_id, video_name, df, size):
    folder_name = '{0}-{1}'.format(video_id, video_name)
    ffmpeg_file_path = '{0}/ffmpeg_concat.txt'.format(folder_name)
    if os.path.exists(ffmpeg_file_path):
        return
    with open(ffmpeg_file_path, 'a') as f:
        last_time = 0
        last_file_path = ''
        for index, row in df.iterrows():
            # if not first, write duration.
            # Note: time is in milliseconds.
            duration = float(row['time']) / 1000 - last_time
            if index != 0:
                f.write(f'duration {duration:.3f}\n')
            file_path = get_image_file_path(folder_name, row['time'], row['image.name'], size)
            f.write("file '{0}'\n".format(file_path))
            last_time = float(row['time']) / 1000
            last_file_path = file_path
        # add some time for the last slide, we have no information how long it should be shown.
        f.write('duration 30\n')
        # Due to a quirk, the last image has to be specified twice - the 2nd time without any duration directive
        # see: https://trac.ffmpeg.org/wiki/Slideshow
        # still not bug free
        f.write("file '{0}'\n".format(last_file_path))


def create_pdf(df, size):
    folder_name = '{0}-{1}'.format(video_id, video_name)
    image_file_paths = [get_image_file_path(folder_name, row['time'], row['image.name'], size) for _, row in df.iterrows()]
    image_handlers = list(map(Image.open, image_file_paths))
    pdf_file_path = os.path.join(folder_name, f'{folder_name}.pdf')
    assert len(image_handlers), 'There are no images.'
    image_handlers[0].save(pdf_file_path, "PDF" ,resolution=100.0, save_all=True, append_images=image_handlers[1:])


parser = argparse.ArgumentParser()
parser.add_argument('url')
parser.add_argument('--size', default='big', help='medium or big')
parser.add_argument('--useragent', default='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/76.0.3809.100 Chrome/76.0.3809.100 Safari/537.36')
parser.add_argument('--basedataurl', default='https://d2ygwrecguqg66.cloudfront.net/data/presentations/')
parser.add_argument('--waittime', default='0.2', type=float, help='seconds to wait after each download')
args = parser.parse_args()

headers = {'User-Agent': args.useragent}
base_img_url = '{0}{1}'.format(args.basedataurl, '{0}/slides/{2}/{1}.jpg')

video_id, video_name = get_video_id(args.url)
json_file = download_slides_json(args.basedataurl, video_id, video_name, headers, args.waittime)
df = parse_json(json_file)
create_ffmpeg_concat_file(video_id, video_name, df, args.size)
download_slides(video_id, video_name, df, base_img_url, args.size, headers, args.waittime)
create_pdf(df, args.size)
