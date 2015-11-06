#!/usr/bin/python

import wand

wand.juju('ensure-availability -n 3')
