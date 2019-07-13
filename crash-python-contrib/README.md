---

### Disclaimer

This is an experimental repo created under my personal account for
demonstration purposes. By no means the code in this repo should be
considered complete or used in a production environment.

---

# sdb
[WIP] The Slick/Simple Debugger

A debugging tool that leverages `gdb`'s Command and Type API (Python)
to implement "pipeable" commands and walkers effectively bringing
these ideas from Solaris/Illumos `mdb` to Linux. Even though most of
the code in this repo can be used with vanilla `gdb`, it is most
useful when used on top of our variant of
[crash-python](github.com/jeffmahoney/crash-python) to debug crash
dumps and live-systems. This is the reason why the code in this
experimental repo is organized in the same file hierachy, so it can
be copied directly in the `crash-python` codebase. Since we've also
introduced a few changes to `crash-python` separately from this repo,
we've provided a diff file that can be modified accordingly and applied
to the original `crash-python` repo.

### Acknowledgements

Most of this work was done in the span of a week during a hackathon
by multiple people whose commit history is lost in this repo. Their
names are listed below (in alphabetic order by last name):

Matthew Ahrens, Don Brady, Paul Dagnelie, John Gallagher, Sara Hartse,
Prashanth Sreenivasa, Prakash Surya, George Wilson, Pavel Zakharov
