#!/usr/bin/python

import argparse
import datetime
import httplib2
import json
import math
import os
import re

from wand import exceptions
from wand.color import Color
from wand.drawing import Drawing
from wand.image import Image


class PhotoFrameFormatter:
	FONT = "RobotoCondensed-Regular.ttf"
	FILL_COLOR = Color("#fff")
	STROKE_COLOR = Color("#000")
	FONT_SIZE = 24
	ORIENTATION_TO_ROTATION = {
		"8": 270,
		"3": 180,
		"6": 90
	}
	DIRECTIONS_TO_SIGNS = {
		"n": 1,
		"e": 1,
		"s": -1,
		"w": -1
	}
	SPLIT_REGEX = re.compile(r",\s*")
	TAKEN_AT_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"
	DISPLAY_DATE_FORMAT = "%b %d '%y, %H:%M"
	REVERSE_GEOCDOING_URL_FORMAT = "https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={key}&result_type=neighborhood"

	def __init__(self, source_dir, output_dir, max_width, max_height, api_key):
		self.source_dir = source_dir
		self.output_dir = output_dir
		self.max_width = max_width
		self.max_height = max_height
		self.api_key = api_key
		self.http = httplib2.Http(".httplib2_cache")

	def format_files(self):
		for root, dirs, files in os.walk(self.source_dir):
			for f in files:
				if f.startswith("."):
					continue
				file_path = os.path.join(root, f)
				try:
					self.format_file(file_path=file_path)
				except (exceptions.TypeError, exceptions.MissingDelegateError, exceptions.BlobError), e:
					print "Error with %s: %s" % (file_path, e)

	def format_file(self, file_path):
		with Image(filename=file_path).clone() as img:
			orientation = 1
			taken_at = latitude = longitude = latitude_sign = longitude_sign = location = ""

			for key, value in img.metadata.items():
				lower_key = key.lower()
				if lower_key == "exif:orientation":
					orientation = value
				elif lower_key == "exif:gpslatitude":
					latitude = value
				elif lower_key == "exif:gpslongitude":
					longitude = value
				elif lower_key == "exif:gpslatituderef":
					latitude_sign = self.DIRECTIONS_TO_SIGNS[value.lower()]
				elif lower_key == "exif:gpslongituderef":
					longitude_sign = self.DIRECTIONS_TO_SIGNS[value.lower()]
				elif lower_key == "exif:datetimeoriginal":
					taken_at = datetime.datetime.strptime(value, self.TAKEN_AT_DATE_FORMAT)

			if orientation in self.ORIENTATION_TO_ROTATION:
				img.rotate(self.ORIENTATION_TO_ROTATION[orientation])

			if latitude and latitude_sign and longitude and longitude_sign and self.api_key:
				decimal_latitude = self.dms_to_decimal(dms=latitude, sign=latitude_sign)
				decimal_longitude = self.dms_to_decimal(dms=longitude, sign=longitude_sign)
				location = self.reverse_geocode(latitude=decimal_latitude, longitude=decimal_longitude)
				location = ",".join((location.split(",", 3))[0:-1])

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

			text = ""
			if taken_at:
				text = taken_at.strftime(self.DISPLAY_DATE_FORMAT)
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
					draw.stroke_width = 0.5
					draw.text(x=math.trunc(new_width / 2), y=self.FONT_SIZE, body=text)
					draw(img)

			new_file = file_path.replace(os.sep, "").replace(".", "").replace(" ", "") + ".jpg"
			img.save(filename=os.path.join(self.output_dir, new_file))

	def dms_to_decimal(self, dms, sign):
		factor = 1
		total = 0

		for fraction in re.split(self.SPLIT_REGEX, dms):
			numerator, denominator = fraction.split("/")
			quotient = float(numerator) / float(denominator) / factor
			total += quotient
			factor *= 60

		return sign * total

	def reverse_geocode(self, latitude, longitude):
		url = self.REVERSE_GEOCDOING_URL_FORMAT.format(
			latitude=latitude, longitude=longitude, key=self.api_key)
		headers, content = self.http.request(url, "GET")
		results = json.loads(content)
		try:
			return results["results"][0]["formatted_address"]
		except KeyError:
			return ""


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Batch format images.")
	parser.add_argument("--source", type=str, default=".",
		help="The parent directory. Will be scanned recursively for images.")
	parser.add_argument("--output", type=str, default="/tmp",
		help="Directory in which formatted images will be saved.")
	parser.add_argument("--max-width", type=int, default=800,
		help="Maximum width of the resized image. Aspect ratio will be preserved.")
	parser.add_argument("--max-height", type=int, default=600,
		help="Maximum height of the resized image. Aspect ratio will be preserved.")
	parser.add_argument("--api-key", type=str,
		help="An optional API key. If present, reverse geocoding will be used to assign locations to images. See https://developers.google.com/maps/documentation/geocoding/#api_key")

	args = parser.parse_args()
	photo_frame_formatter = PhotoFrameFormatter(source_dir=args.source, output_dir=args.output,
		max_width=args.max_width, max_height=args.max_height, api_key=args.api_key)
	photo_frame_formatter.format_files()