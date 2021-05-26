# archsetup 

Setup scripts for my personal laptop (a thinkpad t495) running on archlinux. 
Most of the scripts are hightly customized for my setup.


![the actual desktop](static/desktop.png)

## rationale

![obligatory xkcd](https://imgs.xkcd.com/comics/wanna_see_the_code.png)

First of all, it is mostly to satisfy my urge as a software engineer to automate everything. 

For the provisioning part, I used Ansible which I wanted to learn so I consider this automation 
a learning exercise. 

But it's still provide me some benefits for my day-to-day:

- dotfiles managements without other toolings (`GNU stow`, ...)
- self-documentation of my setup
- easily replicable & shareable

## structure

The setup is structured in two folders: [`install`](install/) and [`provision`](provision/)

### `install`

`install` contains a custom installation script using [`Archinstall`](https://wiki.archlinux.org/title/Archinstall).

#### usage

> TODO: investigate how to create an custom archiso with the custom installation script included
 to avoid the hacky `run.sh`

After booting the archlinux installer, `git clone` this repo and run: 

```sh
./install/run.sh thinkpad_t495
```

You will need to answer 3 questions: which disk to use for the installation? what is the root password? what is the user password?

And then, the script was executed in less than 1 minutes 30 seconds on my laptop. 

**WARNING** it will completely re-format the disk you picked to install archlinux! So, you will loose all of your data

### `provision`

`provision` contains a Ansible role to setup my laptop the way I want it. It includes various configuration files, 
custom wallpaper, GNOME customization, ...

Probably the most interesting part is the custom role to download and build AUR packages to a local repository ([source](provision/roles/aur-build)).
Unlike [kewlfft/ansible-aur](https://github.com/kewlfft/ansible-aur), this module don't need to create a user who 
can execute `pacman` without password. This module also don't need any AUR helpers. Since the module cannot execute 
`pacman`, the module cannot install build time dependencies. Those need to be installed before hands but in practice, 
if you stick with simple/common AUR packages, you rarely need advanced dependencies.

#### usage

```sh
cd ./provision && ./run.sh
```
