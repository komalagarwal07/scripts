#!/bin/bash
SHELL=/bin/bash
PATH=/usr/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
set -x

if [[ $# -eq 0 || ! (("$1" == 'prod') || ("$1" == 'staging')) ]];
then
	echo "Input argument needs to be one of 'prod' or 'staging'!"
	exit 1
fi

time_start=`date +%s`
dump_folder_name=`date "+%Y-%m-%d-%H.mongo_dump"`
dump_file_name=`date "+%Y-%m-%d-%H.mongo.tar.gz"`
backup_dir='/mnt/backups/mongo_backup'
s3_bucket="gobasco-$1/tech-backups"
if [ "$1" == 'prod' ];
then
	host_ip='172.31.19.132'
else
	host_ip='172.31.28.11'
fi

EMAIL="dev@gobasco.com"
LOGFILE='/var/log/mongo_backup.log'

f_log() {
  echo "$dump_file_name:$1" >> $LOGFILE
}
f_info() {
  echo "$1"
  f_log "info: $1"
}

f_error() {
  f_log "Error : $1"
  echo "Error :$1" | /usr/bin/mail -s "Mongo Backup Failed" $EMAIL
  exit 1
}

#Mongo backup
cd ${backup_dir}
mongodump --host ${host_ip} -o ${dump_folder_name}
tar czf ${dump_file_name} ${dump_folder_name} --remove-files
if [ $? == 0 ];
then
        f_info "Mongo Backup Completed"
else
        f_error "Mongo Backup Failed"
fi


#list files
cd ${backup_dir}
file=`ls -utlr ${backup_dir}/ | head -2 | tail -1| awk '{print $9}' | cut -d '/' -f3`

#Upload Backup on s3
aws s3 cp ${file} s3://${s3_bucket}/mongo/
if [ $? == 0 ];
then
        f_info "Backup files transferred to S3.. ${file}"
else
        f_error "Backup failed while transferring files to S3.. ${file}"
fi

#delete file from local if exist on s3
file_exists_in_s3=$(aws s3 ls s3://${s3_bucket}/mongo/${file}| awk '{print $4}')
if [ ${file_exists_in_s3} ==  ${file} ];
then
	f_info "${file} exists in s3 and deleting from local `rm -r ${backup_dir}/${file}`"
else
	f_error "${file} doesn't exist in s3 and hence could not delete it from local"
fi


time_end=`date +%s`
execution_time=`expr $(( $time_end - $time_start ))`
echo "Script Execution time is $execution_time seconds....."
