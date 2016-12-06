#!/bin/bash
# Use CRAN to install IRKernel from git
R -e "install.packages(c('repr', 'IRdisplay', 'evaluate', 'crayon', 'pbdZMQ', 'devtools', 'uuid', 'digest'), repos='http://cran.rstudio.com')"
R -e "devtools::install_github('IRkernel/IRkernel')"
