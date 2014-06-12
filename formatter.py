#!/usr/bin/python

import datetime
import httplib2
import json
import math
import os
import re
import sys

from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow
from wand.color import Color
from wand.drawing import Drawing
from wand.image import Image

class GooglePlusImage:
	DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

	def __init__(self, http, entry):
		if "gphoto$originalvideo" in entry:
			self.image = None
			return

		headers, content = http.request(entry["media$group"]["media$content"][0]["url"], "GET")
		self.image = Image(blob=content)

		self.filename = entry["title"]["$t"]

		self.datetime = datetime.datetime.strptime(entry["published"]["$t"], self.DATETIME_FORMAT)

		try:
			lat_long = entry["georss$where"]["gml$Point"]["gml$pos"]["$t"]
		except KeyError:
			self.latitude = self.longitude= None
		else:
			self.latitude, self.longitude = lat_long.split(" ")

		self.rotation_degrees = 0


class FileImage:
	DIRECTIONS_TO_SIGNS = {
		"n": 1,
		"e": 1,
		"s": -1,
		"w": -1
	}
	TAKEN_AT_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

	def __init__(self, file_path):
		try:
			self.image = Image(filename=self.file_path)
		except Exception:
			self.image = None
			return

		self.filename = file_path.replace(os.sep, "").replace(".", "").replace(" ", "") + ".jpg"

		latitude = longitude = latitude_sign = longitude_sign = None
		for key, value in self.image.metadata.items():
			lower_key = key.lower()
			if lower_key == "exif:orientation":
				if value == "8":
					self.rotation_degrees = 270
				elif value == "3":
					self.rotation_degrees = 180
				elif value == "6":
					self.rotation_degrees = 90
				else:
					self.rotation_degrees = 0
			elif lower_key == "exif:gpslatitude":
				latitude = value
			elif lower_key == "exif:gpslongitude":
				longitude = value
			elif lower_key == "exif:gpslatituderef":
				latitude_sign = self.DIRECTIONS_TO_SIGNS[value.lower()]
			elif lower_key == "exif:gpslongituderef":
				longitude_sign = self.DIRECTIONS_TO_SIGNS[value.lower()]
			elif lower_key == "exif:datetimeoriginal":
				self.datetime = datetime.datetime.strptime(value, self.TAKEN_AT_DATE_FORMAT)

		if latitude and longitude and latitude_sign and longitude_sign:
			self.latitude = self.dms_to_decimal(dms=latitude, sign=latitude_sign)
			self.longitude = self.dms_to_decimal(dms=longitude, sign=longitude_sign)
		else:
			self.latitude = self.longitude= None

	@staticmethod
	def dms_to_decimal(dms, sign):
		factor = 1
		total = 0

		for fraction in re.split(re.compile(r",\s*"), dms):
			numerator, denominator = fraction.split("/")
			quotient = float(numerator) / float(denominator) / factor
			total += quotient
			factor *= 60

		return sign * total


class PhotoFrameFormatter:
	GOOGLE_PLUS = "google+"
	CLIENT_SECRETS_FILE = "client_secrets.json"
	PICASA_WEB_ALBUMS_SCOPE = "https://picasaweb.google.com/data/"
	PICASA_WEB_ALUMBS_RECENT_PHOTOS_URL = "https://picasaweb.google.com/data/feed/api/user/default?kind=photo&alt=json&imgmax=d&max-results=100"
	FILL_COLOR = Color("#fff")
	STROKE_COLOR = Color("#000")
	STROKE_WIDTH = 0.5
	FONT_SIZE = 24
	FONT = os.path.join(os.path.dirname(os.path.realpath(__file__)),
		"RobotoCondensed-Regular.ttf")
	DISPLAY_DATE_FORMAT = "%b %d '%y, %H:%M"
	REVERSE_GEOCDOING_URL_FORMAT = "https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={key}&result_type=neighborhood"

	def __init__(self, args, source, output_dir, max_width, max_height, api_key, no_text):
		self.args = args
		self.source = source
		self.output_dir = output_dir
		self.max_width = max_width
		self.max_height = max_height
		self.api_key = api_key
		self.no_text = no_text
		self.http = None

	def authenticate_http(self):
	  flow = flow_from_clientsecrets(self.CLIENT_SECRETS_FILE, scope=self.PICASA_WEB_ALBUMS_SCOPE)
	  storage = Storage("%s-oauth2.json" % sys.argv[0])
	  credentials = storage.get()
	  if credentials is None or credentials.invalid:
	    credentials = run_flow(flow, storage, self.args)

	  self.http = credentials.authorize(httplib2.Http(".httplib2_cache"))

	def format_photos(self):
		if self.source == self.GOOGLE_PLUS:
			if not self.http:
				self.authenticate_http()

			headers, content = self.http.request(self.PICASA_WEB_ALUMBS_RECENT_PHOTOS_URL, "GET")
			feed = json.loads(content)
			for entry in feed["feed"]["entry"]:
				try:
					self.process_image(GooglePlusImage(self.http, entry))
				except Exception, e:
					print e
		else:
			for root, dirs, files in os.walk(self.source):
				for f in files:
					if not f.startswith("."):
						try:
							self.process_image(FileImage(os.path.join(root, f)))
						except Exception, e:
							print e

	def process_image(self, image):
		if not image.image:
			return

		with image.image.clone() as img:
			if image.rotation_degrees:
				img.rotate(image.rotation_degrees)

			original_width, original_height = img.size
			ratio = float(original_width) / float(original_height)

			if ratio > self.max_width / self.max_height:
				new_width = self.max_width
				new_height = self.max_width / ratio
			else:
				new_height = self.max_height
				new_width = self.max_height * ratio

			img.resize(math.trunc(new_width), math.trunc(new_height))
			img.format = "jpeg"

			if not self.no_text:
				text = ""
				if image.latitude and image.longitude:
					location = self.reverse_geocode(latitude=image.latitude, longitude=image.longitude)
					location = ",".join(location.split(",")[0:2])
				else:
					location = ""
				if image.datetime:
					text = image.datetime.strftime(self.DISPLAY_DATE_FORMAT)
				if location:
					text += " @ " + location

				if text:
					with Drawing() as draw:
						draw.font = self.FONT
						draw.text_antialias = True
						draw.font_size = self.FONT_SIZE
						draw.stroke_color = self.STROKE_COLOR
						draw.fill_color = self.FILL_COLOR
						draw.text_alignment = "center"
						draw.stroke_width = self.STROKE_WIDTH
						draw.text(x=math.trunc(new_width / 2), y=self.FONT_SIZE, body=text)
						draw(img)

			img.save(filename=os.path.join(self.output_dir, image.filename))

	def reverse_geocode(self, latitude, longitude):
		url = self.REVERSE_GEOCDOING_URL_FORMAT.format(
			latitude=latitude, longitude=longitude, key=self.api_key)

		if not self.http:
			self.http = httplib2.Http(".httplib2_cache")

		try:
			headers, content = self.http.request(url, "GET")
			results = json.loads(content)
			return results["results"][0]["formatted_address"]
		except Exception:
			return ""


if __name__ == "__main__":
	argparser.add_argument("--source", type=str, default=".",
		help="The parent directory, or the string '%s' to use Google+ photos." % PhotoFrameFormatter.GOOGLE_PLUS)
	argparser.add_argument("--destination", type=str, default="/tmp",
		help="Directory in which formatted images will be saved.")
	argparser.add_argument("--max-width", type=int, default=800,
		help="Maximum width of the resized image. Aspect ratio will be preserved.")
	argparser.add_argument("--max-height", type=int, default=600,
		help="Maximum height of the resized image. Aspect ratio will be preserved.")
	argparser.add_argument("--no-text", action="store_true", default=False,
		help="Flag that disables the text overlays with date and location.")
	argparser.add_argument("--api-key", type=str,
		help="An optional API key. If present, reverse geocoding will be used to assign locations to images. See https://developers.google.com/maps/documentation/geocoding/#api_key")

	args = argparser.parse_args()
	photo_frame_formatter = PhotoFrameFormatter(args=args, source=args.source, output_dir=args.destination,
		max_width=args.max_width, max_height=args.max_height, api_key=args.api_key, no_text=args.no_text)
	photo_frame_formatter.format_photos()