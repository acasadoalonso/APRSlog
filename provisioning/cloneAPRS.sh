#!/bin/bash
rm html
sudo rm -r public
git clone https://github.com/acasadoalonso/SGP-2D-Live-Tracking.git 			public
git clone https://github.com/acasadoalonso/SGP-2D-Live-Tracking-data-gathering.git 	public/main
ln -s public html
ls -la