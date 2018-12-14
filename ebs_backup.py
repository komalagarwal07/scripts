import boto3
import datetime
import logging
import re
import time
import os
import sys

if len(sys.argv) < 2 or sys.argv[1] not in ['mumbai', 'virginia']:
	print "Input argument needs to be one of 'mumbai' or 'virginia'!"
	sys.exit()

if sys.argv[1] == 'mumbai':
	REGION_NAME = 'ap-south-1'
	INSTANCE_LIST = ['i-0d8ca1e7c79d6f5b0','i-0d278b54cad6a08a0','i-0cc09994d01bcec13']
else:
	REGION_NAME = 'us-east-1'
	INSTANCE_LIST = ['i-08a79037857978bcf']

#creating name for ebs snapshot
def get_snapshot_name(instance, dev):
        snapshot_name = ""
        if 'Tags' in instance:
                for tag in instance['Tags']:
                        if tag['Key'] == 'Name':
                                snapshot_name = tag['Value']
        if snapshot_name:
		snapshot_name = snapshot_name + "-" + dev['DeviceName']
	else:
                snapshot_name = instance['InstanceId']
        return snapshot_name


#setup simple logging for INFO
logger = logging.getLogger()
logger.setLevel(logging.ERROR)
debugMode = False
cleanDate = datetime.datetime.now()-datetime.timedelta(days=5)
ec2 = boto3.client('ec2', region_name=REGION_NAME)
reservations = ec2.describe_instances(
    InstanceIds=INSTANCE_LIST,
).get(
  'Reservations', []
)
instances = sum(
    [
        [i for i in r['Instances']]
        for r in reservations
    ], []
)
## create volume backup based on InstanceID
ec2 = boto3.resource('ec2', region_name=REGION_NAME)
print "Located %d instances for backup" % len(instances)
for instance in instances:
    for dev in instance['BlockDeviceMappings']:
        if dev.get('Ebs', None) is None:
            # Skipping none EBS Volumes
            continue
        vol_id = dev['Ebs']['VolumeId']
        print "Found EBS Volume %s on instance %s" % (
            vol_id, instance['InstanceId']
        )
        description = str(datetime.datetime.now()) + "-" + vol_id + "-automated"
        snapshots = ec2.create_snapshot(
		VolumeId=vol_id, 
		Description=description,
		TagSpecifications=[{
        		'ResourceType': 'snapshot',
        		'Tags': [{
            			'Key': 'Name',
            			'Value': get_snapshot_name(instance, dev)
        		}]
    		}]
	)
        print(snapshots)
        tags = snapshots.create_tags(Resources=[snapshots.id], Tags=[{'Key': 'costcenter', 'Value': 'EbsBackup'}])
        print tags

print "[LOG] Cleaning out old entries starting on " + str(cleanDate)
for snap in ec2.snapshots.all():

        #verify snapshots to be those created by this backup script
        if snap.description.endswith("-automated"):

            #Pull the snapshot date
            snapDate = snap.start_time.replace(tzinfo=None)
            if debugMode == True:
                print("[DEBUG] " + str(snapDate) +" vs " + str(cleanDate))

            #Compare the clean dates
            if cleanDate > snapDate:
                print("[INFO] Deleting: " + snap.id + " - From: " + str(snapDate))
                if debugMode != True:
                    try:
                        snapshot = snap.delete()
                    except:

                        #if we timeout because of a rate limit being exceeded, give it a rest of a few seconds
                        print("[INFO]: Waiting 5 Seconds for the API to Chill")
                        time.sleep(5)
                        snapshot = snap.delete()
			print("[INFO] " + str(snapshot))

