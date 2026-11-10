# My Phone on F-Droid

The app is distributed as a signed `.apk` on **GitHub Releases**
(`android-v<version>` tags, built by `.github/workflows/android-release.yml`).
This page is the checklist for getting it into F-Droid as well.

## Already in place

- **Store listing in the repo**: `fastlane/metadata/android/en-US/`
  (title, short and full description, icon, screenshots, and
  `changelogs/<versionCode>.txt`; versionCode = major*10000 + minor*100 + patch,
  so 0.9.0 is `900`). F-Droid reads these straight from the source.
- **No Google services**, no analytics, no ads, no proprietary push.
- **No dependency metadata blob** in the APK (`dependenciesInfo` off), which
  F-Droid requires.
- **Update check can be switched off at build time**: F-Droid builds with
  `-Pmyphone.updateCheck=false`, so the app never offers a GitHub `.apk` (it
  couldn't install over an F-Droid-signed app anyway). Settings then says
  "Updates: Delivered by F-Droid". The app also recognises installs from
  F-Droid clients (F-Droid, Droid-ify, Neo Store) and leaves updates to them.
- **Tags** look like `android-v0.9.0`, so F-Droid's update checker can follow
  them (`UpdateCheckMode: Tags ^android-v.*$`).

## The one blocker for the main F-Droid repository: Linphone

Calls use the Linphone SDK (`org.linphone.no-video:linphone-sdk-android`),
downloaded as a ready-made `.aar` from Linphone's own Maven repository
(`download.linphone.org`). F-Droid's main repository builds everything from
source and only accepts binaries from Maven Central / Google's Maven, so
before it can be listed there, one of these has to happen:

1. **Build the Linphone SDK from source in the F-Droid recipe** (the way
   F-Droid builds the Linphone app itself). Heavy, but the "proper" route.
2. **Switch the calling engine** to a library F-Droid can build.

## Faster option: your own F-Droid repository

You can publish your own F-Droid repo (people add it once in the F-Droid
app, and then get updates there) without waiting for review, and the
prebuilt Linphone SDK isn't a problem there:

1. `pip install fdroidserver` (or the Debian `fdroidserver` package).
2. `mkdir repo && cd repo && fdroid init` (creates a signing key; back it up).
3. Copy the release `.apk` from GitHub into `repo/repo/`, then
   `fdroid update -c` and `fdroid deploy` (to GitHub Pages, your web
   server, etc.).
4. Share the repo address (or its QR code) with your users.

Or apply to **IzzyOnDroid**, a large third-party repo that ships the APK from
GitHub Releases as-is (it accepts prebuilt libraries like Linphone's).

## Draft recipe for the main repository (once Linphone is solved)

```yaml
Categories: [Phone & SMS, Connectivity]
License: GPL-2.0-or-later
SourceCode: https://github.com/DanversKara/OwnPBX.org
IssueTracker: https://github.com/DanversKara/OwnPBX.org/issues
AutoName: My Phone
RepoType: git
Repo: https://github.com/DanversKara/OwnPBX.org
Builds:
  - versionName: 0.9.0
    versionCode: 900
    commit: android-v0.9.0
    subdir: android/app
    gradle: [yes]
    gradleprops: [myphone.updateCheck=false]
AutoUpdateMode: Version
UpdateCheckMode: Tags ^android-v.*$
CurrentVersion: 0.9.0
CurrentVersionCode: 900
```
