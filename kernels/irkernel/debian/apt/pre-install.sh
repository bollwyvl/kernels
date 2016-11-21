#!/bin/bash
apt-get update -q
apt-get install -y -q r-base r-base-dev
R -e "install.packages(c('repr', 'IRdisplay', 'evaluate', 'crayon', 'pbdZMQ', 'devtools', 'uuid', 'digest'))"
R -e "devtools::install_github('IRkernel/IRkernel')"
