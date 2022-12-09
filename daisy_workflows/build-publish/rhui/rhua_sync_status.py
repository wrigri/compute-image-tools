#  Copyright 2022 Google Inc. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http:#www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""Publish metrics for RHUA sync status."""

import os
import subprocess
import time

import requests


REPODIR = '/var/lib/rhui/remote_share/symlinks/pulp/content/content'


def GetRepodataList(dirname):
  # Use "find" here because os.walk takes ~30 minutes,
  # while find takes 10-30 seconds.
  cmd = ['find', dirname, '-name', 'repodata']
  output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  return output.stdout.split()


def PublishMetric(metric_type, points, access_token, mig_name):
  region = GetRegion()
  url = ('https://monitoring.googleapis.com/v3/projects/'
         'google.com%3Arhel-infra/timeSeries')
  headers = {'Authorization': 'Bearer {}'.format(access_token)}
  metric = {'type': metric_type}
  resource_labels = {'project_id': '155767908850',
                     'location': region,
                     'namespace': 'rhua-sync-status',
                     'node_id': mig_name}
  resource = {'type': 'generic_node',
              'labels': resource_labels}

  time_series = [{'metric': metric,
                  'resource': resource,
                  'points': points}]

  data = {'timeSeries': time_series}
  print(data)
  r = requests.post(url, json=data, headers=headers)
  print(r.text)


def PublishRepoAge(seconds_since_update, timestamp, access_token, mig_name):
  print(seconds_since_update)
  end_time = time.strftime('%Y-%m-%dT%H:%M:%S-00:00', time.gmtime(timestamp))
  metric_type = 'custom.googleapis.com/rhua_sync_age'

  points = [{'interval': {'endTime': end_time},
             'value': {'int64Value': seconds_since_update}}]

  PublishMetric(metric_type, points, access_token, mig_name)


def PublishRecentUpdates(recent_updates, access_token, mig_name):
  if not recent_updates:
    return
  metric_type = 'custom.googleapis.com/rhua_updates'
  points = []
  for update in recent_updates:
    end_time = time.strftime('%Y-%m-%dT%H:%M:%S-00:00', time.gmtime(update))
    point = {'interval': {'endTime': end_time}, 'value': {'boolValue': True}}
    points.append(point)

  PublishMetric(metric_type, points, access_token, mig_name)


def PublishLastHourCount(hour_count, timestamp, access_token, mig_name):
  print(hour_count)
  end_time = time.strftime('%Y-%m-%dT%H:%M:%S-00:00', time.gmtime(timestamp))
  metric_type = 'custom.googleapis.com/rhua_updates_in_hour'

  points = [{'interval': {'endTime': end_time},
             'value': {'int64Value': hour_count}}]

  PublishMetric(metric_type, points, access_token, mig_name)


def GetAccessToken():
  url = ('http://metadata.google.internal/computeMetadata/v1/instance/'
         'service-accounts/default/token')
  headers = {'Metadata-Flavor': 'Google'}
  r = requests.get(url, headers=headers)
  access_token = r.json()['access_token']
  return access_token


def GetMIGName():
  url = ('http://metadata.google.internal/computeMetadata/v1/instance/'
         'attributes/created-by')
  headers = {'Metadata-Flavor': 'Google'}
  r = requests.get(url, headers=headers)
  full_path = r.text
  mig_name = full_path.split('/')[-1]
  return mig_name


def GetRegion():
  url = 'http://metadata.google.internal/computeMetadata/v1/instance/zone'
  headers = {'Metadata-Flavor': 'Google'}
  r = requests.get(url, headers=headers)
  zone = r.text.split('/')[-1]
  zone_split = zone.split('-')
  region = '-'.join(zone_split[:-1])
  return region


def main():
  newest = 0.0
  now = time.time()
  hour_ago = now - 3600
  five_min_ago = now - 300
  hour_count = 0
  recent_updates = []

  repodata_list = GetRepodataList(REPODIR)

  for repodata in repodata_list:
    statinfo = os.stat(repodata)
    if statinfo.st_mtime > hour_ago:
      hour_count += 1
    if statinfo.st_mtime > five_min_ago:
      recent_updates.append(statinfo.st_mtime)
    if statinfo.st_mtime > newest:
      newest = statinfo.st_mtime

  repo_age = int(now - newest)
  access_token = GetAccessToken()
  print(access_token)
  mig_name = GetMIGName()
  print(mig_name)
  region = GetRegion()
  print(region)

  PublishRepoAge(repo_age, now, access_token, mig_name)
  PublishLastHourCount(hour_count, now, access_token, mig_name)
  PublishRecentUpdates(recent_updates, access_token, mig_name)


if __name__ == '__main__':
  main()
