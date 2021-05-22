import archinstall
import time
import logging

def install(hostname: str):
    input('Press Enter to start the installation.')
    archinstall.do_countdown()

    archinstall.arguments['harddrive'].keep_partitions = False

    with archinstall.Filesystem(archinstall.arguments['harddrive'], archinstall.GPT) as fs:
        fs.use_entire_disk(root_filesystem_type='btrfs')

        root = fs.find_partition('/')
        root.format(root.filesystem)
        root.mount('/mnt', options='compress-force=zstd')

        boot = fs.find_partition('/boot')
        boot.format('vfat')
        boot.mount('/mnt/boot')


    archinstall.use_mirrors({'Netherlands': archinstall.list_mirrors()['Netherlands']})

    with archinstall.Installer('/mnt') as installation:
        installation.log(f'Waiting for automatic mirror selection (reflector) to complete.', level=logging.INFO)
        while archinstall.service_state('reflector') not in ('dead', 'failed'):
            time.sleep(1)

        if not installation.minimal_installation():
            raise RuntimeError('Failed to perform execute the minimal installation')
        installation.set_hostname(hostname)
        installation.set_keyboard_language('fr')
        installation.set_timezone('Europe/Brussels')
        installation.add_bootloader()

        # Setup networkmanager
        installation.add_additional_packages('networkmanager')
        installation.enable_service('NetworkManager.service')

        installation.add_additional_packages('ansible', 'git')

        installation.user_create('charles', archinstall.arguments['!charles-password'], sudo=True)
        installation.user_set_pw('root', archinstall.arguments['!root-password'])


def ask_questions():
    while archinstall.arguments.get('harddrive') is None:
        archinstall.arguments['harddrive'] = archinstall.select_disk(archinstall.all_disks())
        if archinstall.arguments.get('harddrive') is None:
            print('You must select a harddrive')

    while archinstall.arguments.get('!root-password') is None:
        archinstall.arguments['!root-password'] = archinstall.get_password(prompt='Enter root password: ')
        if archinstall.arguments.get('!root-password') is None:
            print('password for user `root` is required')

    while archinstall.arguments.get('!charles-password') is None:
        archinstall.arguments['!charles-password'] = archinstall.get_password(prompt='Enter charles password: ')
        if archinstall.arguments.get('!charles-password') is None:
            print('password for user `charles` is required')


ask_questions()
install('charles-laptop')