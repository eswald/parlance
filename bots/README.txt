Parang Diplomacy Clients
========================

About Parang
------------

Parang is a set of clients that can play the `Diplomacy`_ board game over a
network, using the `Parlance`_ framework.

This software may be reused for non-commercial purposes without charge,
and without notifying the authors.  Use of any part of this software for
commercial purposes without permission from the authors is prohibited.

.. _Diplomacy: http://en.wikipedia.org/wiki/Diplomacy_%20game%20
.. _Parlance: http://sourceforge.net/projects/parlance/


Commands
--------

Parang installs the following commands:

blabberbot
  A simple bot that sends constant streams of random press.

chatty
  A console-based game observer.

combobot
  A very slow bot with an unproven thinking strategy.

dumbbot
  A port of David Norman's DumbBot, which was written in two days.

evilbot
  A cheating version of DumbBot, which identifies its clones.

neurotic
  A neural-network bot, which unfortunately has no memory yet.

peacebot
  A simple bot that invites each player to be peaceful.

project20m
  A port of Andrew Huff's Project20M, formerly the best DAIDE bot available.

parang-config
  Prints out an example configuration file.


Installation
------------

Parang can be installed with `Easy Install`_ from a command prompt::

    > easy_install parang

Alternatively, once you have downloaded and unpacked a source distribution, you
can install it with::

    > python setup.py install

.. _Easy Install: http://peak.telecommunity.com/DevCenter/EasyInstall


Credits
-------

* David Norman wrote the original C code for DumbBot.

* Andrew Huff, Vincent Chan, Laurence Tondelier, Damian Bundred, and Colm Egan
  wrote the original Java code for Project20M, probably based on DumbBot.

* Neil Schemenauer wrote the neural network module used by Neurotic.

* Eric Wald ported DumbBot and Project20M to the Parlance framework, wrote
  the order-submission engines for ComboBot and Neurotic, convinced EvilBot to
  cheat, and wrote the press engines for BlabberBot and PeaceBot.
