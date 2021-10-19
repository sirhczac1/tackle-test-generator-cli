# ***************************************************************************
# Copyright IBM Corporation 2021
#
# Licensed under the Eclipse Public License 2.0, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ***************************************************************************

import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from tkltest.util import constants, coverage_util, build_util, command_util
from tkltest.util.logging_util import tkltest_status


def augment_with_code_coverage(config, ctd_build_file, ctd_test_dir, dev_build_file,
                               dev_written_test_dir, evosuite_test_dir, augment_dir, report_dir):
    """Augments CTD-guided tests with coverage-increasing base tests.

    Starting with the CTD-guided and base test suites, iteratively augments the CTD-guided test
    suite by adding each test class generated by the base test generator that increases code
    coverage achieved by the test suite. The augmentation is done in two passes. In the first pass,
    the coverage increment of each test class over the coverage of the initial test suite is
    computed. Test classes that do not increase coverage are discarded; the remaining test classes
    are sorted based on decreasing order of coverage increments. In the second pass, the initial
    test suite is augmented by adding one test class at a time: this is done by processing each
    test class in the sorted order and adding the test class to the test suite if it increases
    the coverage of the augmented test suite.

    Args:
        config (dict): loaded and validated config information
        ctd_build_file (str): Build file to use for running tests
        ctd_test_dir (str): Root directory for CTD tests
        dev_build_file (str): Build file to use for running developer-written tests
        dev_written_test_dir (str): Root directory for developer-written tests
        evosuite_test_dir (str): Root directory for evosuite tests (the augmentation pool)
        augment_dir (str): Directory name to use for the augmented test suite
        report_dir (str): Main reports directory, under which coverage report is generated
    """
    tkltest_status('Performing coverage-driven test-suite augmentation and optimization')

    # generate evosuite build file
    gen_config_file = os.path.join(ctd_test_dir, '.tkltest_generate.toml')
    shutil.copy(gen_config_file, evosuite_test_dir)
    config['general']['test_directory'] = os.path.basename(evosuite_test_dir)
    evo_build_file, _ = build_util.generate_build_xml(app_name=config['general']['app_name'],
                                                      monolith_app_path=config['general']['monolith_app_path'],
                                                      app_classpath=build_util.get_build_classpath(config),
                                                      test_root_dir=evosuite_test_dir, test_dirs=[evosuite_test_dir],
                                                      partitions_file=None, target_class_list=[],
                                                      main_reports_dir=config['general']['reports_path'],
                                                      app_packages=config['execute']['app_packages'],
                                                      collect_codecoverage=True, offline_instrumentation=True)

    # build everything (assumes dev-written build file has target `merge-coverage-report`)
    for build_file in [ctd_build_file, dev_build_file, evo_build_file]:
        if build_file:
            command_util.run_command("ant -f {} merge-coverage-report".format(build_file), verbose=False)

    classes = []
    prefix = len(os.path.basename(evosuite_test_dir))
    for cls in Path(evosuite_test_dir).glob(f'**/*.java'):
        class_name = str(cls)[prefix + 1:]
        class_name = re.sub('_?(ES)?Test.java', '', class_name)
        if '_scaffolding' not in class_name:
            classes.append(class_name)
    print(classes)

    for class_name in classes:
        command_util.run_command(f'ant -f {evosuite_test_dir}/my_own_build.xml execute-tests -Dclass={class_name}',
                                 verbose=True)

    # TODO:
    #  * We now have jacoco files at (1) {ctd_test_dir}/merged_jacoco.exec,
    #                                (2) {dev_written_test_dir}/merged_jacoco.exec, and
    #                                (3) {evosuite_test_dir}/package_path_to_Class_jacoco.exec
    #                                    for each class `package.path.to.Class` in {classes}.
    #  1. Merge jacoco files (1) and (2) to get a merged file (4) and run jacoco report to get seed test suite coverage.
    #  2. For every cls in {classes}, merge its jacoco file (3) with (4) and compare coverage,
    #      saving stats to a dictionary {cls: class_stats}.
    #  3. Go over classes from highest coverage gain to lowest, and continue as before
    #      (comparing by merging jacoco files instead of actually executing each time).
    #  4. Once we have the chosen class names in a format like `package_path_to_Class_jacoco.exec`,
    #      we can easily retrieve the paths by globbing `**/package/path/to/Class*.java` (with scaffolding/JEE-support).
    #  5. What is left is to copy all the CTD tests, the dev-written tests, and the chosen tests to a new directory,
    #      and to create a new build file that calls the original CTD/EvoSuite build file and the user-supplied one,
    #      and merges the coverage as we have done.

