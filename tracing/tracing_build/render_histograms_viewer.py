# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cgi
import json
import logging
import re

_DATA_START = '<div id="histogram-json-data" style="display:none;"><!--'
_DATA_END = '--!></div>'
# If you change this, please update "Fall-back to old formats."
_JSON_TAG = '<histogram-json>%s</histogram-json>'


def ExtractJSON(results_html):
  results = []
  flags = re.MULTILINE | re.DOTALL
  start = re.search("^%s" % re.escape(_DATA_START), results_html, flags)
  if start is None:
    logging.warn('Could not find histogram data start: %s', _DATA_START)
    return []
  pattern = '^((%s)|(.*?))$' % re.escape(_DATA_END)
  # Find newlines and parse each line as separate JSON data.
  for match in re.compile(pattern, flags).finditer(results_html, start.end()+1):
    try:
      # Check if the end tag in group(2) got a match.
      if match.group(2):
        return results
      results.append(json.loads(match.group(3)))
    except ValueError:
      logging.warn(
          'Found existing results json, but failed to parse it: %s',
          match.group(1))
      return []
  return results

def ExtractLegacyJSON(results_html, json_tag):
  results = []
  pattern = '(.*?)'.join(re.escape(part) for part in json_tag.split('%s'))
  flags = re.MULTILINE | re.DOTALL
  for match in re.finditer(pattern, results_html, flags):
    try:
      results.append(json.loads(match.group(1)))
    except ValueError:
      logging.warn(
          'Found existing results json, but failed to parse it: %s',
          match.group(1))
      return []
  return results


def ReadExistingResults(results_html):
  if not results_html:
    return []

  histogram_dicts = ExtractJSON(results_html)

  # Fall-back to old formats.
  if not histogram_dicts:
    logging.warn('Using fallback format')
    histogram_dicts = ExtractLegacyJSON(results_html, _JSON_TAG)
  if not histogram_dicts:
    histogram_dicts = ExtractLegacyJSON(
        results_html, json_tag='<div class="histogram-json">%s</div>')
  if not histogram_dicts:
    match = re.search('<div id="value-set-json">(.*?)</div>', results_html,
                      re.MULTILINE | re.DOTALL)
    if match:
      histogram_dicts = json.loads(match.group(1))

  if not histogram_dicts:
    logging.warn('Failed to extract previous results from HTML output')
  return histogram_dicts


def RenderHistogramsViewer(histogram_dicts, output_stream, reset_results=False,
                           vulcanized_html=''):
  """Renders a Histograms viewer to output_stream containing histogram_dicts.

  Requires a Histograms viewer to have already been vulcanized.
  The vulcanized viewer can be provided either as a string or a file.

  Args:
    histogram_dicts: list of dictionaries containing Histograms.
    output_stream: file-like stream to read existing results and write HTML.
    reset_results: whether to drop existing results.
    vulcanized_html: HTML string of vulcanized histograms viewer.
  """
  output_stream.seek(0)

  if not reset_results:
    results_html = output_stream.read()
    output_stream.seek(0)
    histogram_dicts += ReadExistingResults(results_html)

  output_stream.write(vulcanized_html)
  # Put all the serialized histograms nodes inside an html comment to avoid
  # unecessary stress on html parsing and avoid creating throw-away dom nodes.
  output_stream.write(_DATA_START)
  for histogram in histogram_dicts:
    hist_json = json.dumps(histogram, separators=(',', ':'))
    output_stream.write('\n')
    output_stream.write(cgi.escape(hist_json))
  output_stream.write('\n%s\n' % _DATA_END)

  # If the output file already existed and was longer than the new contents,
  # discard the old contents after this point.
  output_stream.truncate()
