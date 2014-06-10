#!/usr/bin/python

import argparse
import datetime
import math
import os

from wand.image import Image
from wand import exceptions

ORIENTATION_TO_ROTATION = {
	"8": 270,
	"3": 180,
	"6": 90
}

def main(source_dir, output_dir, max_width, max_height):
	for root, dirs, files in os.walk(source_dir):
		for file in files:
			if file.startswith("."):
				continue
			file_path = os.path.join(root, file)
			try:
				format_file(file_path=file_path, output_dir=output_dir,
					max_width=max_width, max_height=max_height)
			except (exceptions.TypeError, exceptions.MissingDelegateError, exceptions.BlobError), e:
				print "Error with %s: %s" % (file_path, e)

def format_file(file_path, output_dir, max_width, max_height):
	with Image(filename=file_path).clone() as img:
		orientation = 1
		for key, value in img.metadata.items():
			if key.lower() == "exif:orientation":
				orientation = value

		if orientation in ORIENTATION_TO_ROTATION:
			img.rotate(ORIENTATION_TO_ROTATION[orientation])

		original_width, original_height = img.size
		ratio = float(original_width) / float(original_height)

		if ratio > max_width / max_height:
			new_width = max_width
			new_height = max_width / ratio
		else:
			new_height = max_height
			new_width = max_height * ratio

		img.resize(math.trunc(new_width), math.trunc(new_height))
		img.format = "jpeg"
		new_file = file_path.replace(os.sep, "").replace(".", "").replace(" ", "") + ".jpg"
		img.save(filename=os.path.join(output_dir, new_file))


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

	args = parser.parse_args()
	main(source_dir=args.source, output_dir=args.output, max_width=args.max_width,
		max_height=args.max_height)