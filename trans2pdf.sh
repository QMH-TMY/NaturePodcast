#!/bin/bash
# 批量转换当前目录下txt为同名pdf

for file in `ls $1`;do 
	if [ "${file##*.}" = "txt" ]
	then
		pandoc -t latex -o "$1${file%.*}.pdf" $1${file} 2> error.txt
		/bin/rm $1${file}  #删除.txt文件
	fi
done
