import pytest
import os
import re


securedrop_test_vars = pytest.securedrop_test_vars


def extract_package_name_from_filepath(filepath):
    """
    Helper function to infer intended package name from
    the absolute filepath, using a rather garish regex.
    E.g., given:
       securedrop-ossec-agent-2.8.2+0.3.10-amd64.deb

    retuns:

       securedrop-ossec-agent

    which can then be used for comparisons in dpkg output.
    """
    deb_basename = os.path.basename(filepath)
    package_name = re.search('^([a-z\-]+(?!\d))', deb_basename).groups()[0]
    assert deb_basename.startswith(package_name)
    return package_name


def get_deb_packages():
    """
    Helper function to retrieve module-namespace test vars and format
    the strings to interpolate version info. Keeps the test vars DRY
    in terms of version info, and required since we can't rely on
    Jinja-based evaluation of the YAML files (so we can't trivially
    reuse vars in other var values, as is the case with Ansible).
    """
    substitutions = dict(
            securedrop_version=securedrop_test_vars.securedrop_version,
            ossec_version=securedrop_test_vars.ossec_version,
            keyring_version=securedrop_test_vars.keyring_version,
            )

    deb_packages = [d.format(**substitutions) for d in securedrop_test_vars.build_deb_packages]
    return deb_packages


deb_packages = get_deb_packages()

@pytest.mark.parametrize("deb", deb_packages)
def test_build_deb_packages(File, deb):
    """
    Sanity check the built Debian packages for Control field
    values and general package structure.
    """
    deb_package = File(deb.format(
        securedrop_test_vars.securedrop_version))
    assert deb_package.is_file


@pytest.mark.parametrize("deb", deb_packages)
def test_deb_packages_appear_installable(File, Command, Sudo, deb):
    """
    Confirms that a dry-run of installation reports no errors.
    Simple check for valid Debian package structure, but not thorough.
    When run on a malformed package, `dpkg` will report:

       dpkg-deb: error: `foo.deb' is not a debian format archive

    Testing application behavior is left to the functional tests.
    """

    deb_package = File(deb.format(
        securedrop_test_vars.securedrop_version))

    deb_basename = os.path.basename(deb_package.path)
    package_name = extract_package_name_from_filepath(deb_package.path)
    assert deb_basename.startswith(package_name)

    # Sudo is required to call `dpkg --install`, even as dry-run.
    with Sudo():
        c = Command("dpkg --install --dry-run {}".format(deb_package.path))
        assert "Selecting previously unselected package {}".format(package_name) in c.stdout
        regex = "Preparing to unpack [./]+{} ...".format(re.escape(deb_basename))
        assert re.search(regex, c.stdout, re.M)
        assert c.rc == 0


@pytest.mark.parametrize("deb", deb_packages)
def test_deb_package_control_fields(File, Command, deb):
    """
    Ensure Debian Control fields are populated as expected in the package.
    These checks are rather superficial, and don't actually confirm that the
    .deb files are not broken. At a later date, consider integration tests
    that actually use these built files during an Ansible provisioning run.
    """
    deb_package = File(deb.format(
        securedrop_test_vars.securedrop_version))
    package_name = extract_package_name_from_filepath(deb_package.path)
    # The `--field` option will display all fields if none are specified.
    c = Command("dpkg-deb --field {}".format(deb_package.path))

    assert "Maintainer: SecureDrop Team <securedrop@freedom.press>" in c.stdout
    assert "Architecture: amd64" in c.stdout
    assert "Package: {}".format(package_name) in c.stdout
    assert c.rc == 0


@pytest.mark.parametrize("deb", deb_packages)
def test_deb_package_control_fields_homepage(File, Command, deb):
    deb_package = File(deb.format(
        securedrop_test_vars.securedrop_version))
    # The `--field` option will display all fields if none are specified.
    c = Command("dpkg-deb --field {}".format(deb_package.path))
    assert "Homepage: https://securedrop.org" in c.stdout


@pytest.mark.parametrize("deb", deb_packages)
def test_deb_package_contains_no_pyc_files(File, Command, deb):
    """
    Ensures no .pyc files are shipped via the Debian packages.
    """
    deb_package = File(deb.format(
        securedrop_test_vars.securedrop_version))
    # Using `dpkg-deb` but `lintian --tag package-installs-python-bytecode`
    # would be cleaner. Will defer to adding lintian tests later.
    c = Command("dpkg-deb --contents {}".format(deb_package.path))
    assert not re.search("^.*\.pyc$", c.stdout, re.M)


@pytest.mark.parametrize("deb", deb_packages)
def test_deb_package_contains_no_config_file(File, Command, deb):
    """
    Ensures the `securedrop-app-code` package does not ship a `config.py`
    file. Doing so would clobber the site-specific changes made via Ansible.

    Somewhat lazily checking all deb packages, rather than just the app-code
    package, but it accomplishes the same in a DRY manner.
    """
    deb_package = File(deb.format(
        securedrop_test_vars.securedrop_version))
    # Using `dpkg-deb` but `lintian --tag package-installs-python-bytecode`
    # would be cleaner. Will defer to adding lintian tests later.
    c = Command("dpkg-deb --contents {}".format(deb_package.path))
    assert not re.search("^.*config\.py$", c.stdout, re.M)


@pytest.mark.parametrize("deb", deb_packages)
def test_securedrop_app_code_is_reproducible(File, Command, LocalCommand, deb):
    """
    Ensures the `securedrop-app-code` package build process is deterministic,
    specifically that multiple runs with the same source code will create
    deb packages with identical checksums.
    """

    # Prepare dict for storing results of repeated builds.
    package_checksums = {}

    deb_package = File(deb.format(
        securedrop_test_vars.securedrop_version))

    if "securedrop-app-code" in deb_package.path:
        # Build 3 times and compare output of each file.
        for i in range(1, 4):
            # No need to build on the first iteration; we've already done that
            # as part of the provisioning run.
            if i != 1:
                LocalCommand("vagrant provision build")
            # Store temporary deb package for later analysis, otherwise
            # subsequent builds will clobber output.
            temporary_deb = "~/app-code-{}.deb".format(i)
            cmd = "cp {} {}".format(deb_package.path, temporary_deb)
            Command.check_output(cmd)

            package_checksums[i] = File(temporary_deb).sha256sum

        assert package_checksums[1] == package_checksums[2]
        assert package_checksums[2] == package_checksums[3]
