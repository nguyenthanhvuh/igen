# #Otter
# prog="vsftpd"
# echo ${prog}
# python2.7 igen.py ${prog}  --logger_level 4 --seed 100 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1

# prog="ngircd"
# echo ${prog}
# python2.7 igen.py ${prog}  --logger_level 4 --seed 0 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1

#CoreUtils
prog="id"
echo ${prog}
python2.7 igen.py ${prog}  --logger_level 4 --seed 0 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1

prog="uname"
echo ${prog}
python2.7 igen.py ${prog}  --logger_level 4 --seed 0 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1

prog="mv"
echo ${prog}
python2.7 igen.py ${prog}  --logger_level 4 --seed 0 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1

prog="cat"
echo ${prog}
python2.7 igen.py ${prog}  --logger_level 4 --seed 0 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1

prog="ln"
echo ${prog}
python2.7 igen.py ${prog}  --logger_level 4 --seed 0 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1

prog="date"
echo ${prog}
python2.7 igen.py ${prog}  --logger_level 4 --seed 0 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1

prog="sort"
echo ${prog}
python2.7 igen.py ${prog}  --logger_level 4 --seed 0 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1

prog="ls"
echo ${prog}
python2.7 igen.py ${prog}  --logger_level 4 --seed 0 --benchmark 20 > ~/Dropbox1/config_results/${prog}_bm20 2>&1
