#!/usr/bin/env python

from __future__ import print_function
import argparse
import os
import os.path
import sys
if sys.version_info[0] < 3:
    import ConfigParser as configparser
else:
    import configparser
import subprocess
import multiprocessing
import shutil


CTNG_URL = 'https://github.com/crosstool-ng/crosstool-ng.git'
CTNG_TAG = 'crosstool-ng-1.23.0'

DIR_ROOT = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
DIR_OUTPUT = os.path.join(DIR_ROOT, 'output')
DIR_CTNG = os.path.join(DIR_ROOT, 'ctng')
DIR_TARBALLS = os.path.join(DIR_ROOT, 'tarballs')

TAG_INI_SECTION_CONFIG = 'CONFIG'
TAG_INI_TOOLCHAIN_NAME = 'TOOLCHAIN_NAME'
TAG_INI_SECTION_CTNG   = 'CROSSTOOL'


def mkdir_safe(dname):
    if os.path.exists(dname):
        return
    try:
        os.makedirs(dname)
    except:
        if os.path.exists(dname):
            return
        raise


def load_ini_config(path):
    config = configparser.RawConfigParser()
    config.optionxform=str
    config.read(path)
    return config


def get_ini_conf_string1(config, section, option):
    return config.get(section, option).strip()


def touch_file(fname):
    with open(fname, mode='a') as _:
        pass


def ctng_bootstrap():
    if os.path.isdir(DIR_CTNG):
        shutil.rmtree(DIR_CTNG)
    mkdir_safe(DIR_CTNG)
    print ("> Clone '{0}' in '{1}'".format(CTNG_URL, DIR_CTNG))
    subprocess.check_call(["git", "clone", CTNG_URL, "."], cwd=DIR_CTNG)
    print ("> Switch on tag '{0}' in '{1}'".format(CTNG_TAG, DIR_CTNG))
    subprocess.check_call(["git", "checkout", 'tags/{0}'.format(CTNG_TAG)], cwd=DIR_CTNG)
    print ("> CTNG BOOTSTRAP")
    subprocess.check_call([os.path.join(DIR_CTNG, 'bootstrap')], cwd=DIR_CTNG)
    print ("> CTNG CONFIGURE")
    subprocess.check_call([os.path.join(DIR_CTNG, 'configure'), '--enable-local'], cwd=DIR_CTNG)
    print ("> CTNG MAKE")
    subprocess.check_call(['make'], cwd=DIR_CTNG)


def build_toolchain(ct_config):
    toolchain_name = get_ini_conf_string1(ct_config, TAG_INI_SECTION_CONFIG, TAG_INI_TOOLCHAIN_NAME)
    dir_obj = os.path.join(DIR_OUTPUT, 'obj', toolchain_name)
    dir_prefix = os.path.join(DIR_OUTPUT, 'x-tools', toolchain_name)
    defcfg_template = os.path.join(dir_obj, 'crosstool.config')
    ctng_tool = os.path.join(DIR_CTNG, 'ct-ng')

    mkdir_safe(dir_obj)
    mkdir_safe(DIR_TARBALLS)

    build_stamp_file = os.path.join(DIR_OUTPUT, '{0}.stamp'.format(toolchain_name))

    if not os.path.isfile(build_stamp_file):
        with open(defcfg_template, mode='wt') as fh:
            ct_options = ct_config.options(TAG_INI_SECTION_CTNG)
            for ct_opt_name in ct_options:
                ct_opt_value = get_ini_conf_string1(ct_config, TAG_INI_SECTION_CTNG,ct_opt_name)
                print("{0}={1}".format(ct_opt_name, ct_opt_value), file=fh)
            print('CT_PREFIX_DIR="{0}"'.format(dir_prefix), file=fh)
            print('CT_LOCAL_TARBALLS_DIR="{0}"'.format(DIR_TARBALLS), file=fh)

        print ("> Generate config for '{0}'".format(toolchain_name))
        custom_env = {}
        custom_env.update(os.environ)
        custom_env['DEFCONFIG'] = defcfg_template
        subprocess.check_call([ctng_tool, 'defconfig'], cwd=dir_obj, env=custom_env)

        print ("> Running build for '{0}'".format(toolchain_name))
        cpu_count = multiprocessing.cpu_count()
        subprocess.check_call([ctng_tool, 'build.{0}'.format(cpu_count)], cwd=dir_obj)
        subprocess.check_call(['chmod', '-R', 'u+w', dir_prefix])

        items_to_remove = [ os.path.join(dir_prefix, 'build.log.bz2') ]
        for rm_item in items_to_remove:
            if os.path.isfile(rm_item):
                os.remove(rm_item)

        touch_file(build_stamp_file)

    toolchain_tgz = os.path.join(DIR_OUTPUT, '{0}.tgz'.format(toolchain_name))
    print ("> Packaging in '{0}'".format(toolchain_tgz))
    tar_argv = ['tar', '-czf', toolchain_tgz, '--owner=0', '--group=0', os.path.basename(dir_prefix) ]
    subprocess.check_call(tar_argv, cwd=os.path.dirname(dir_prefix))



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', nargs=1, required=True)
    args = parser.parse_args()
    config_file = args.config[0]
    init_only = False
    if config_file == '-':
        init_only = True

    if not init_only and not os.path.isfile(config_file):
        print("ERROR: File not found - '{0}'".format(config_file))
        exit(1)

    mkdir_safe(os.path.join(DIR_OUTPUT))
    ctng_stamp = os.path.join(DIR_OUTPUT, 'ctng.stamp')
    if not os.path.isfile(ctng_stamp):
        ctng_bootstrap()
        touch_file(ctng_stamp)

    if init_only:
        exit(0)

    ct_config = load_ini_config(config_file)
    toolchain_name = get_ini_conf_string1(ct_config, TAG_INI_SECTION_CONFIG, TAG_INI_TOOLCHAIN_NAME)

    toolchain_tgz = os.path.join(DIR_OUTPUT, '{0}.tgz'.format(toolchain_name))
    if not os.path.isfile(toolchain_tgz):
        build_toolchain(ct_config)

    print ("> Published as '{0}'".format(toolchain_tgz))
