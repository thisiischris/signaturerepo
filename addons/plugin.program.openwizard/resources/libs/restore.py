################################################################################
#      Copyright (C) 2015 Surfacingx                                           #
#                                                                              #
#  This Program is free software; you can redistribute it and/or modify        #
#  it under the terms of the GNU General Public License as published by        #
#  the Free Software Foundation; either version 2, or (at your option)         #
#  any later version.                                                          #
#                                                                              #
#  This Program is distributed in the hope that it will be useful,             #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of              #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the                #
#  GNU General Public License for more details.                                #
#                                                                              #
#  You should have received a copy of the GNU General Public License           #
#  along with XBMC; see the file COPYING.  If not, write to                    #
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.       #
#  http://www.gnu.org/copyleft/gpl.html                                        #
################################################################################

import xbmc
import xbmcgui
import xbmcvfs

import json
import os
import re
import time

import six

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

if six.PY3:
    import zipfile
elif six.PY2:
    from resources.libs import zipfile

from resources.libs.common import logging
from resources.libs.common import tools
from resources.libs.common.config import CONFIG

LAST_URLBUILD_BUILD_KEY = 'lasturlbuild_build'
LAST_URLBUILD_GUI_KEY = 'lasturlbuild_gui'
UPDATE_URL_BUILD_KEY = 'urlupdate_build'
UPDATE_URL_GUI_KEY = 'urlupdate_gui'
UPDATE_URLS_FILENAME = 'update_urls.json'


def _update_urls_store_path():
    base = xbmcvfs.translatePath('special://profile/')
    folder = os.path.join(base, 'OpenWizard')
    if not xbmcvfs.exists(folder):
        try:
            xbmcvfs.mkdirs(folder)
        except Exception:
            pass
    return os.path.join(folder, UPDATE_URLS_FILENAME)


def _read_update_urls_file():
    path = _update_urls_store_path()
    if not xbmcvfs.exists(path):
        return '', ''
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        return str(data.get('build', '') or '').strip(), str(data.get('gui', '') or '').strip()
    except Exception:
        logging.log('[Update URLs] Could not read {0}'.format(path), level=xbmc.LOGWARNING)
        return '', ''


def _write_update_urls_file(build_url, gui_url):
    path = _update_urls_store_path()
    payload = {'build': build_url or '', 'gui': gui_url or ''}
    try:
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)
        logging.log('[Update URLs] Saved to {0}'.format(path))
    except Exception as err:
        logging.log('[Update URLs] Could not write {0}: {1}'.format(path, err), level=xbmc.LOGERROR)


def _uservar_default_update_urls():
    return CONFIG.DEFAULT_UPDATE_BUILD_URL, CONFIG.DEFAULT_UPDATE_GUI_URL


def _apply_update_url_settings(build_url, gui_url):
    CONFIG.set_setting(UPDATE_URL_BUILD_KEY, build_url or '')
    CONFIG.set_setting(UPDATE_URL_GUI_KEY, gui_url or '')
    _write_update_urls_file(build_url, gui_url)


def ensure_update_urls_loaded():
    """Restore saved Update URLs after wizard reinstall or empty settings."""
    bu = _stored_update_url(UPDATE_URL_BUILD_KEY)
    gu = _stored_update_url(UPDATE_URL_GUI_KEY)

    file_bu, file_gu = _read_update_urls_file()
    if not bu and file_bu:
        bu = file_bu
        CONFIG.set_setting(UPDATE_URL_BUILD_KEY, bu)
    if not gu and file_gu:
        gu = file_gu
        CONFIG.set_setting(UPDATE_URL_GUI_KEY, gu)
    if (file_bu or file_gu) and (bu or gu):
        logging.log('[Update URLs] Restored from profile store')

    default_bu, default_gu = _uservar_default_update_urls()
    if not bu and default_bu:
        bu = default_bu
        CONFIG.set_setting(UPDATE_URL_BUILD_KEY, bu)
    if not gu and default_gu:
        gu = default_gu
        CONFIG.set_setting(UPDATE_URL_GUI_KEY, gu)
    if (default_bu or default_gu) and (bu or gu):
        logging.log('[Update URLs] Applied defaults from uservar.py')

    if bu or gu:
        _write_update_urls_file(bu, gu)

    return bu, gu


def read_update_urls():
    ensure_update_urls_loaded()
    return _read_hardcoded_update_urls()


def clear_update_urls():
    CONFIG.set_setting(UPDATE_URL_BUILD_KEY, '')
    CONFIG.set_setting(UPDATE_URL_GUI_KEY, '')
    CONFIG.set_setting(LAST_URLBUILD_BUILD_KEY, '')
    CONFIG.set_setting(LAST_URLBUILD_GUI_KEY, '')
    path = _update_urls_store_path()
    if xbmcvfs.exists(path):
        try:
            xbmcvfs.delete(path)
        except Exception:
            pass


def _stored_update_url(key):
    v = CONFIG.get_setting(key)
    if v in (False, None):
        return ''
    return str(v).strip()


def _save_last_urlbuild_pair(pairs):
    """Remember URLs from [Restore] URL Build for main-menu Update."""
    if not pairs:
        return
    CONFIG.set_setting(LAST_URLBUILD_BUILD_KEY, pairs[0][0])
    CONFIG.set_setting(LAST_URLBUILD_GUI_KEY, pairs[1][0] if len(pairs) > 1 else '')


def _read_hardcoded_update_urls():
    """Fixed URLs set from main menu → Update → Set Update URLs."""
    return _stored_update_url(UPDATE_URL_BUILD_KEY), _stored_update_url(UPDATE_URL_GUI_KEY)


def update_urls_configured():
    bu, gu = _read_hardcoded_update_urls()
    return bool(bu and gu)


def _is_http_url(url):
    try:
        scheme = urlparse(url).scheme.lower()
    except (AttributeError, TypeError, ValueError):
        return False
    return scheme in ('http', 'https')


def _normalize_backup_url(url):
    """Prefer direct download for Dropbox shared links (dl=1)."""
    if not url:
        return url
    url = url.strip()
    if 'dropbox.com' not in url.lower():
        return url
    if re.search(r'[?&]dl=0(?:&|$)', url, re.I):
        return re.sub(r'dl=0', 'dl=1', url, count=1, flags=re.I)
    if not re.search(r'[?&]dl=1(?:&|$)', url, re.I):
        url = url + ('&' if '?' in url else '?') + 'dl=1'
    return url


def _zip_name_from_source(file, external):
    if external and _is_http_url(file):
        base = os.path.basename(urlparse(file).path.rstrip('/'))
        if base.lower().endswith('.zip'):
            return base
        return 'restore_{0}.zip'.format(int(time.time()))
    display = os.path.split(file)
    return display[1]


def _is_valid_zip_file(path):
    try:
        with open(path, 'rb') as f:
            if f.read(4) != b'PK\x03\x04':
                return False
        with zipfile.ZipFile(path, 'r', allowZip64=True) as zf:
            return len(zf.namelist()) > 0
    except Exception:
        return False


def _binary_queue_path():
    return os.path.join(CONFIG.USERDATA, 'build_binaries.txt')


def _read_binary_install_queue():
    binarytxt = _binary_queue_path()
    if not os.path.exists(binarytxt):
        return []
    raw = tools.read_from_file(binarytxt).strip()
    if not raw:
        return []
    return [addon_id.strip() for addon_id in raw.split(',') if addon_id.strip()]


def _remove_binary_install_queue():
    binarytxt = _binary_queue_path()
    if not os.path.exists(binarytxt):
        return
    try:
        os.remove(binarytxt)
    except Exception:
        try:
            xbmcvfs.delete(binarytxt)
        except Exception:
            pass


def _addon_is_installed(addon_id):
    return xbmc.getCondVisibility('System.HasAddon({0})'.format(addon_id))


def sync_binary_install_queue():
    """Clear stale queue after restore or when everything is already installed."""
    pending = _read_binary_install_queue()
    if not pending:
        _remove_binary_install_queue()
        return []

    missing = [addon_id for addon_id in pending if not _addon_is_installed(addon_id)]
    if not missing:
        logging.log('[Binary Detection] Queue cleared — all listed add-ons already installed')
        _remove_binary_install_queue()
        return []

    return missing


def binaries():
    missing = sync_binary_install_queue()
    if not missing:
        logging.log("[Binary Detection] No pending binary add-ons to install")
        return True

    dialog = xbmcgui.Dialog()
    logging.log("[Binary Detection] Reinstalling {0} binary add-on(s)".format(len(missing)))
    dialog.ok(CONFIG.ADDONTITLE,
              '[COLOR {0}]The restored build lists platform-specific add-ons that still need to be '
              'installed. Use the remote to confirm each install dialog. Cancelling may leave '
              'streams or devices unsupported.[/COLOR]'.format(CONFIG.COLOR2))

    success = []
    fail = []

    from resources.libs.gui import addon_menu

    for addon_id in missing:
        if _addon_is_installed(addon_id):
            logging.log('{0} already installed.'.format(addon_id))
            success.append(addon_id)
            continue
        if addon_menu.install_from_kodi(addon_id):
            logging.log('{0} install succeeded.'.format(addon_id))
            success.append(addon_id)
        else:
            logging.log('{0} install failed.'.format(addon_id))
            fail.append(addon_id)

    still_missing = [addon_id for addon_id in missing if not _addon_is_installed(addon_id)]
    if not still_missing:
        _remove_binary_install_queue()
        if not fail:
            dialog.ok(CONFIG.ADDONTITLE, 'The selected add-ons were all installed successfully.')
        return True

    if fail:
        dialog.ok(
            CONFIG.ADDONTITLE,
            'The following add-ons could not be installed automatically:\n{0}\n\n'
            'Install them from the Kodi Add-on repository, then delete '
            'userdata/build_binaries.txt or run Update again.'.format(', '.join(fail)))
    return False


class Restore:
    def __init__(self, external=False):
        tools.ensure_folders()

        self.external = external
        self.dialog = xbmcgui.Dialog()
        self.progress_dialog = xbmcgui.DialogProgress()

    def _prompt_for_wipe(self):
        # Should we wipe first?
        wipe = self.dialog.yesno(CONFIG.ADDONTITLE,
                                 "[COLOR {0}]Do you wish to restore your".format(CONFIG.COLOR2) + '\n' + "Kodi configuration to default settings" + '\n' + "Before installing the {0} backup?[/COLOR]".format('local' if not self.external else 'external'),
                                 nolabel='[B][COLOR red]No[/COLOR][/B]',
                                 yeslabel='[B][COLOR springgreen]Yes[/COLOR][/B]')

        if wipe:
            from resources.libs import install
            install.wipe()

    def _from_file(self, file, loc):
        from resources.libs import db
        from resources.libs import extract

        filename = _zip_name_from_source(file, self.external)
        # Never stage http downloads under addons/packages: install.wipe() clears that tree
        # before extract when the user chooses to reset first (same reason wizard uses MYBUILDS).
        packages = os.path.join(CONFIG.PACKAGES, filename)
        staging_zip = os.path.join(CONFIG.MYBUILDS, filename) if (
            self.external and _is_http_url(file)) else packages
        if self.external and _is_http_url(file):
            try:
                staging_zip = xbmc.makeLegalFilename(staging_zip)
            except Exception:
                pass
        extract_source = file

        if not self.external:
            try:
                zipfile.ZipFile(file, 'r', allowZip64=True)
            except zipfile.BadZipFile as e:
                from resources.libs.common import logging
                logging.log(e, level=xbmc.LOGERROR)
                self.progress_dialog.update(0, '[COLOR {0}]Unable to read zip file from current location.'.format(CONFIG.COLOR2) + '\n' + 'Copying file to packages')
                xbmcvfs.copy(file, packages)
                file = xbmcvfs.translatePath(packages)
                extract_source = file
                self.progress_dialog.update(0, '\n' + 'Copying file to packages: Complete')
                zipfile.ZipFile(file, 'r', allowZip64=True)
        else:
            if _is_http_url(file):
                try:
                    self.progress_dialog.close()
                except Exception:
                    pass
                from resources.libs.downloader import Downloader
                Downloader().download(file, staging_zip)
                xbmc.sleep(500)
                if not os.path.isfile(staging_zip) or os.path.getsize(staging_zip) == 0:
                    try:
                        os.remove(staging_zip)
                    except Exception:
                        pass
                    logging.log_notify(
                        CONFIG.ADDONTITLE,
                        "[COLOR {0}]Download failed or file is empty[/COLOR]".format(CONFIG.COLOR2))
                    return
                if not _is_valid_zip_file(staging_zip):
                    try:
                        os.remove(staging_zip)
                    except Exception:
                        pass
                    logging.log_notify(
                        CONFIG.ADDONTITLE,
                        "[COLOR {0}]Download is not a valid zip (wrong link or Dropbox still on preview page).[/COLOR]".format(
                            CONFIG.COLOR2))
                    return
                extract_source = xbmcvfs.translatePath(staging_zip)
            else:
                extract_source = file

        self._prompt_for_wipe()

        try:
            self.progress_dialog.close()
        except Exception:
            pass

        percent, errors, error = extract.all(extract_source, loc)
        self._view_errors(percent, errors, error, extract_source)

        CONFIG.set_setting('installed', 'true')
        CONFIG.set_setting('extract', percent)
        CONFIG.set_setting('errors', errors)

        _remove_binary_install_queue()

        if self.external and _is_http_url(file):
            try:
                os.remove(staging_zip)
            except Exception:
                pass

        db.force_check_updates(over=True)

        tools.kill_kodi(
            msg='[COLOR {0}]To save changes, Kodi needs to be force closed. Would you like to continue?[/COLOR]'.format(
                CONFIG.COLOR2))

    def _restore_http_zip_jobs(self, url_loc_pairs):
        """Download each http(s) zip, wipe once, extract in order. Pairs: [(url, loc), ...]."""
        from resources.libs import db
        from resources.libs import extract

        jobs = []
        ts = int(time.time() * 1000)
        for i, (u, loc) in enumerate(url_loc_pairs):
            stag = os.path.join(CONFIG.MYBUILDS, 'restore_url_{0}_{1}.zip'.format(ts, i))
            try:
                stag = xbmc.makeLegalFilename(stag)
            except Exception:
                pass
            jobs.append((u, stag, loc))

        if not jobs:
            return

        logging.log('[Restore URL] restoring {0} archive(s)'.format(len(jobs)), level=xbmc.LOGINFO)

        staged = []
        for url, staging, _loc in jobs:
            try:
                self.progress_dialog.close()
            except Exception:
                pass
            from resources.libs.downloader import Downloader
            Downloader().download(_normalize_backup_url(url), staging)
            xbmc.sleep(400)
            staged.append(staging)
            if not os.path.isfile(staging) or os.path.getsize(staging) == 0 or not _is_valid_zip_file(staging):
                for s in staged:
                    try:
                        os.remove(s)
                    except Exception:
                        pass
                logging.log_notify(
                    CONFIG.ADDONTITLE,
                    "[COLOR {0}]A download failed or is not a valid zip archive.[/COLOR]".format(CONFIG.COLOR2))
                return

        self._prompt_for_wipe()

        try:
            self.progress_dialog.close()
        except Exception:
            pass

        total_errors = 0
        agg_err = ''
        last_pct = 0
        for _url, staging, loc in jobs:
            pct, errors, err = extract.all(xbmcvfs.translatePath(staging), loc)
            last_pct = pct
            total_errors += int(errors)
            agg_err += err or ''

        for _u, staging, _l in jobs:
            try:
                os.remove(staging)
            except Exception:
                pass

        if total_errors >= 1:
            self._view_errors(last_pct, total_errors, agg_err, 'URL restore')

        CONFIG.set_setting('installed', 'true')
        CONFIG.set_setting('extract', str(last_pct))
        CONFIG.set_setting('errors', str(total_errors))

        _remove_binary_install_queue()

        db.force_check_updates(over=True)

        tools.kill_kodi(
            msg='[COLOR {0}]To save changes, Kodi needs to be force closed. Would you like to continue?[/COLOR]'.format(
                CONFIG.COLOR2))

    def _view_errors(self, percent, errors, error, file):
        if int(errors) >= 1:
            if self.dialog.yesno(CONFIG.ADDONTITLE, '[COLOR {0}][COLOR {1}]{2}[/COLOR]'.format(CONFIG.COLOR2, CONFIG.COLOR1, file) + '\n' + 'Completed: [COLOR {0}]{1}{2}[/COLOR] [Errors: [COLOR {3}]{4}[/COLOR]]'.format(CONFIG.COLOR1, percent, '%',CONFIG.COLOR1, errors) + '\n' + 'Would you like to view the errors?[/COLOR]',
                                 nolabel='[B][COLOR red]No Thanks[/COLOR][/B]',
                                 yeslabel='[B][COLOR springgreen]View Errors[/COLOR][/B]'):

                from resources.libs.gui import window
                window.show_text_box("Viewing Errors", error.replace('\t', ''))

    def choose(self, location):
        from resources.libs import skin

        skin.look_and_feel_data('restore')
        external = 'External' if self.external else 'Local'

        file = self.dialog.browseSingle(1, '[COLOR {0}]Select the backup file you want to restore[/COLOR]'.format(
            CONFIG.COLOR2), '' if self.external else 'files', mask='.zip', useThumbs=True,
                                        defaultt=None if self.external else CONFIG.MYBUILDS)

        zip_ok = file.lower().endswith('.zip')
        if self.external and _is_http_url(file):
            path = urlparse(file).path
            zip_ok = path.lower().endswith('.zip')
        if not zip_ok:
            logging.log_notify(CONFIG.ADDONTITLE,
                               "[COLOR {0}]{1} Restore: Cancelled[/COLOR]".format(
                                   CONFIG.COLOR2, external))
            return

        if self.external:
            response = tools.open_url(file, check=True)

            if not response:
                logging.log_notify(CONFIG.ADDONTITLE,
                                   "[COLOR {0}]External Restore: Invalid URL[/COLOR]".format(CONFIG.COLOR2))
                return

        skin.skin_to_default("Restore")
        self.progress_dialog.create(CONFIG.ADDONTITLE, '[COLOR {0}]Installing {1} Backup'.format(CONFIG.COLOR2, external) + '\n' + 'Please Wait[/COLOR]')

        self._from_file(file, location)

    def _prompt_url_build_pair(self, default_build='', default_gui='', require_gui_zip=False):
        """Returns [(build_url, HOME), (gui_url, USERDATA)] or shorter if gui optional; None on cancel/error."""
        build_raw = tools.get_keyboard(
            default=default_build or '',
            heading='[COLOR {0}][1/2] Build backup — paste direct .zip URL[/COLOR]'.format(CONFIG.COLOR2))
        if not build_raw or not build_raw.strip():
            return None
        build_raw = build_raw.strip()

        if require_gui_zip:
            gui_heading = '[COLOR {0}][2/2] GuiFix — paste *_guisettings.zip URL (required)[/COLOR]'.format(
                CONFIG.COLOR2)
        else:
            gui_heading = (
                '[COLOR {0}][2/2] GuiFix — paste *_guisettings.zip URL (optional; blank = build only)[/COLOR]'.format(
                    CONFIG.COLOR2))
        gui_raw = tools.get_keyboard(default=default_gui or '', heading=gui_heading)
        gui_raw = (gui_raw or '').strip()

        if not tools._is_url(build_raw) or not _is_http_url(build_raw):
            logging.log_notify(
                CONFIG.ADDONTITLE,
                "[COLOR {0}]Build URL is not a valid http(s) address.[/COLOR]".format(CONFIG.COLOR2))
            return None
        if require_gui_zip and not gui_raw:
            logging.log_notify(
                CONFIG.ADDONTITLE,
                "[COLOR {0}]GuiFix URL is required.[/COLOR]".format(CONFIG.COLOR2))
            return None
        if gui_raw and (not tools._is_url(gui_raw) or not _is_http_url(gui_raw)):
            logging.log_notify(
                CONFIG.ADDONTITLE,
                "[COLOR {0}]GuiFix URL is not a valid http(s) address.[/COLOR]".format(CONFIG.COLOR2))
            return None

        pairs = [(_normalize_backup_url(build_raw), CONFIG.HOME)]
        if gui_raw:
            pairs.append((_normalize_backup_url(gui_raw), CONFIG.USERDATA))

        for u, _loc in pairs:
            path = urlparse(u).path
            if not path.lower().endswith('.zip'):
                if not self.dialog.yesno(
                        CONFIG.ADDONTITLE,
                        '[COLOR {0}]This URL path does not end in .zip:[/COLOR]\n[COLOR {1}]{2}[/COLOR]\n'
                        'Continue anyway?'.format(CONFIG.COLOR2, CONFIG.COLOR1, u[:120]),
                        nolabel='[B][COLOR red]Cancel[/COLOR][/B]',
                        yeslabel='[B][COLOR springgreen]Continue[/COLOR][/B]'):
                    return None
            if not tools.open_url(u, check=True):
                if not self.dialog.yesno(
                        CONFIG.ADDONTITLE,
                        '[COLOR {0}]Could not verify a link (some hosts block checks). Try download anyway?[/COLOR]'.format(
                            CONFIG.COLOR2),
                        nolabel='[B][COLOR red]Cancel[/COLOR][/B]',
                        yeslabel='[B][COLOR springgreen]Try download[/COLOR][/B]'):
                    logging.log_notify(
                        CONFIG.ADDONTITLE,
                        "[COLOR {0}]Restore from URL: Cancelled[/COLOR]".format(CONFIG.COLOR2))
                    return None

        return pairs

    def restore_from_url(self, location, action='build'):
        from resources.libs import skin

        if action == 'build':
            pairs = self._prompt_url_build_pair(
                default_build=_stored_update_url(LAST_URLBUILD_BUILD_KEY),
                default_gui=_stored_update_url(LAST_URLBUILD_GUI_KEY))
            if not pairs:
                return
            _save_last_urlbuild_pair(pairs)
            skin.look_and_feel_data('restore')
            skin.skin_to_default("Restore")
            self._restore_http_zip_jobs(pairs)
            return

        url_raw = tools.get_keyboard(
            default='',
            heading='[COLOR {0}]Backup .zip URL (http/https; Dropbox dl=1 applied)[/COLOR]'.format(CONFIG.COLOR2))
        if not url_raw:
            return
        url_raw = url_raw.strip()
        if not url_raw:
            return
        if not tools._is_url(url_raw):
            logging.log_notify(CONFIG.ADDONTITLE,
                               "[COLOR {0}]Restore from URL: Invalid URL[/COLOR]".format(
                                   CONFIG.COLOR2))
            return
        if not _is_http_url(url_raw):
            logging.log_notify(CONFIG.ADDONTITLE,
                               "[COLOR {0}]Restore from URL: Only http(s) links are supported[/COLOR]".format(
                                   CONFIG.COLOR2))
            return

        url = _normalize_backup_url(url_raw)
        path = urlparse(url).path
        if not path.lower().endswith('.zip'):
            if not self.dialog.yesno(
                    CONFIG.ADDONTITLE,
                    '[COLOR {0}]The URL path does not end in .zip. Continue anyway?[/COLOR]'.format(CONFIG.COLOR2),
                    nolabel='[B][COLOR red]Cancel[/COLOR][/B]',
                    yeslabel='[B][COLOR springgreen]Continue[/COLOR][/B]'):
                return
        if not tools.open_url(url, check=True):
            if not self.dialog.yesno(
                    CONFIG.ADDONTITLE,
                    '[COLOR {0}]Could not verify the link (some file hosts block automatic checks).[/COLOR]'.format(
                        CONFIG.COLOR2) + '\n' + 'Try downloading anyway?',
                    nolabel='[B][COLOR red]Cancel[/COLOR][/B]',
                    yeslabel='[B][COLOR springgreen]Try download[/COLOR][/B]'):
                logging.log_notify(CONFIG.ADDONTITLE,
                                   "[COLOR {0}]Restore from URL: Cancelled[/COLOR]".format(CONFIG.COLOR2))
                return

        skin.look_and_feel_data('restore')
        skin.skin_to_default("Restore")

        self._from_file(url, location)


def restore(action, external=False, from_url=False):
    cls = Restore(external=external or from_url)

    if from_url:
        if action == 'build':
            cls.restore_from_url(CONFIG.HOME, action='build')
        elif action in ['gui', 'theme', 'addonpack']:
            cls.restore_from_url(CONFIG.USERDATA, action=action)
        elif action == 'addondata':
            cls.restore_from_url(CONFIG.ADDON_DATA, action='addondata')
        return

    if action == 'build':
        cls.choose(CONFIG.HOME)  # Install into special://home/
    elif action in ['gui', 'theme', 'addonpack']:
        cls.choose(CONFIG.USERDATA)  # Install into special://userdata/
    elif action == 'addondata':
        cls.choose(CONFIG.ADDON_DATA)  # Install into special://userdata/addon_data/
    elif action == 'binaries':
        binaries()


def configure_update_urls():
    """Maintenance → Build Update → Update URL: save build + GuiFix links for one-click Update."""
    cls = Restore(external=True)
    bu, gu = read_update_urls()
    pairs = cls._prompt_url_build_pair(
        default_build=bu,
        default_gui=gu,
        require_gui_zip=True)
    if not pairs:
        return
    gui_url = pairs[1][0] if len(pairs) > 1 else ''
    _apply_update_url_settings(pairs[0][0], gui_url)
    _save_last_urlbuild_pair(pairs)
    logging.log_notify(
        CONFIG.ADDONTITLE,
        '[COLOR {0}]Update URLs saved[/COLOR]'.format(CONFIG.COLOR2),
        2500)


def run_stored_build_update():
    """Maintenance → Build Update → Update: download/extract using saved urlupdate_* URLs."""
    cls = Restore(external=True)
    bu, gu = read_update_urls()

    if not bu or not gu:
        cls.dialog.ok(
            CONFIG.ADDONTITLE,
            '[COLOR {0}]Update URLs are not set yet.[/COLOR]\n'
            'Use [COLOR {1}]Maintenance → Build Update → Update URL[/COLOR] to enter your build .zip and GuiFix links.\n'
            'Then [COLOR {1}]Update[/COLOR] always uses those links (saved across reinstalls).'.format(
                CONFIG.COLOR2, CONFIG.COLOR1))
        return

    pairs = [
        (_normalize_backup_url(bu), CONFIG.HOME),
        (_normalize_backup_url(gu), CONFIG.USERDATA)]

    from resources.libs import skin
    skin.look_and_feel_data('restore')
    skin.skin_to_default('Restore')
    cls._restore_http_zip_jobs(pairs)
