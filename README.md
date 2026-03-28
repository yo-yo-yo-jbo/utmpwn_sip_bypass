# A new SIP bypass - UTMPWN
In March 2026, I've decided to look for a new SIP bypasses.  
I've written about SIP [in a previous blogpost](https://github.com/yo-yo-yo-jbo/macos_sip/) and myself have contributed some bypasses over the years.

## SIP bypasses I have reported in the past
To give some context, here are SIP bypasses I have reported in the past:

### Shrootless - CVE-2021-30892
[CVE-2021-30892 (AKA "Shrootless")](https://www.microsoft.com/en-us/security/blog/2021/10/28/microsoft-finds-new-macos-vulnerability-shrootless-that-could-bypass-system-integrity-protection/) was a PackageKit issue in `system_installd`, which is a small wrapper around a private framework known as `PackageKit`.  

#### The issue
I noticed pre/post install package scripts that run `zsh` were running commands from `/etc/zshenv` (or `~/.zshrc`).  
An attacker planting malicious commands in those files could bypass the SIP filesystem protections, as the `zsh` process was inheriting those SIP bypassing capabilities due to being a child process of `system_installd`, which has an entitlement of `com.apple.rootless.install.heritable`.  
I've also talked about it in [Blue Hat Israel in 2022](https://www.youtube.com/watch?v=jBvE0kciSx8).

#### The fix
Apple has added a bunch of mitigations to `zsh` ever since then, and if you look at [zsh/zsh/Src/init.c](https://github.com/apple-oss-distributions/zsh/blob/609ebba9c650c149b46b58b4fe15f828e1e8720e/zsh/Src/init.c) you will see several migitations:

```c
#ifdef __APPLE__
	char *restricted_env = getenv("APPLE_PKGKIT_ESCALATING_ROOT");
	if (restricted_env) {
	    restrict_source = 1;
	}

	uint32_t flags = 0;
	if (!csops(getpid(), CS_OPS_STATUS, &flags, sizeof(flags))) {
		if (flags & CS_INSTALLER) {
			restrict_source = 1;
			fprintf(xtrerr ? xtrerr : stderr,
					"Refusing to load unsafe zshenv.\n");
		}
	} else {
		fprintf(xtrerr ? xtrerr : stderr,
				"Failed to fetch code signing information when loading "
				"zshenv.\n");
	}
#endif /* __APPLE__ */
```

Note how `zsh` checks for both `APPLE_PKGKIT_ESCALATING_ROOT` environment variable and the `csops` status result to see if `CS_INSTALLER` bit is on.

### Migraine - CVE-2023-32369
[CVE-2023-32369 (AKA "Migraine")](https://www.microsoft.com/en-us/security/blog/2023/05/30/new-macos-vulnerability-migraine-could-bypass-system-integrity-protection/) was a `systemmigrationd`-based SIP bypass.

#### The issue
Similarly to `system_installd`, `systemmigrationd` also has `com.apple.rootless.install.heritable`, and I noticed that either `perl` or `bash` could be child processes of it. Unlike before, I've decided to attack the problem from a different angle - environment variable poisoning via either the `PERL5OPT` or `BASH_ENV` environment variables.  
While that was relatively easy, finding ways to trigger the vulnerability without a reboot was quite challenging, and involved reverse engineering and creativity from my partners Michael Pearse and Anurag Bohra, at the time.  
We've done a [DEFCON talk about it](https://www.youtube.com/watch?v=zxZesAN-TEk) (DEFCON 31).

#### The fix
Apple's fixes were much more aggressive and included the following:
1. Strategic fix - no more environment variable poisoning under `launchd` - Apple has decided to basically kill `launchctl setenv` at the time (besides `path` and one other - both of which were sanitized under `systemmigrationd`). It seems since then Apple has retracted their decision but decided to make it impossible to relaunch or even signal to their System daemons, which achieves a similar effect.
2. Hardening `bash`, similarly to what Apple has done with `zsh`.
3. Hardening `perl`: see [perl/5.34/fix
/perl-rootless-v2.patch](https://github.com/apple-oss-distributions/perl/blob/0db21e813bcaf9d04dd2c322c1d90e4178549547/5.34/fix/perl-rootless-v2.patch).
4. Dropping SIP bypassing capabilities via the `csops` call - before calling `bash` or `perl` from `systemmigrationd`.

### CVE-2024-44243
[CVE-2024-44243 (this time I didn't it give a cool name)](https://www.microsoft.com/en-us/security/blog/2025/01/13/analyzing-cve-2024-44243-a-macos-system-integrity-protection-bypass-through-kernel-extensions/) was a `storagekitd`-based SIP bypass.

#### The issue
Just like before, `storagekitd` has `com.apple.rootless.install.heritable`. I noticed in some situations, `storagekitd` calls what seems to be 3rd party executables, e.g. `/Library/Filesystems/iboysoft_NTFS.fs/Contents/Resources/newfs_ms_ntfs`.  
Overriding them was easy and bypasses SIP - the challenge was triggering those without installing a 3rd party software, and involved spoofing a new type of "filesystem" (UserFS) as well as installing 3rd party kernel extensions.

#### The fix
In this case the fix seemed completely tactical: `storagekitd` seemed to drop the SIP bypassing capabilities before calling those binaries.

## Motivation
So, in 2026, the state of SIP is the following:
- Only 3 `com.apple.rootless.install.heritable` binaries on a modern system
  - [Launch Constraints](https://theevilbit.github.io/posts/launch_constraints_deep_dive/) and [Runtime Hardening](https://developer.apple.com/documentation/security/hardened-runtime) prevent many of the old tricks
  - Cannot affect environment variables under launchd anymore
  - Cannot signal protected daemons such as system_installd
- PackageKit is super hardened
  - Many mechanisms to drop SIP before transferring control to scripts
  - Dedicated hardening on `zsh`, `bash` and `perl` that limit scripts and modules that could be run
- [Sealed System Volume (SSV)](https://support.apple.com/guide/security/signed-system-volume-security-secd698747c9/web) basically locks all immutable files under `/System`.
- Technologies such as [PAC](https://developer.apple.com/documentation/Security/preparing-your-app-to-work-with-pointer-authentication) and [MTE](https://security.apple.com/blog/memory-integrity-enforcement/) make running code in the context of privileged processes very unlikely (but not impossible).

Because I am fairly familiar with `systemmigrationd` and `packagekitd`, and since [some researchers](https://github.com/jhftss) keep finding vulnerabilities in PackageKit, I figured finding another `system_installd`-based SIP bypass was a good idea.  
I've decided to download tons of signed packages similarly to how [Iru has done](https://www.iru.com/blog/finding-vulnerabilities-in-apple-packages) in January 2026.

## Failed ideas
I had some ideas that failed:
1. I found issues that rely on a non-root target installation. You can use the `installer` utility to give a different target than /, which affects pre/post install scripts - particularly, argument `$3`. However, I quickly realized that in these situations `installd` is invoked instead of `system_installd`, which makes things a bit pointless for SIP bypassing purposes.
2. I reslized I could affect the `perl` module search order (known as [@INC](https://perldoc.perl.org/variables/@INC)) - in macOS, when `perl` is launched it will search for the file `/Library/Perl/5.34/PrependToPath` (there is also `/Library/Perl/5.34/AppendToPath`) and add all modules there to `@INC`. I confirmed this happens always (including when `perl` has SIP bypassing capabilities). However, Apple has introduced several [patches](https://github.com/apple-oss-distributions/perl/blob/0db21e813bcaf9d04dd2c322c1d90e4178549547/5.34/fix/perl-rootless-check-fd.patch) to perl that make untrusted modules not load, so I could not do a "module hijacking" on Perl.
3. I noticed pre/post install scripts that start with `#!/bin/sh` ended up running `bash` instead! Apparently, `/bin/sh` is not a real shell on macOS - it will consult a symlink under `/private/var/select/sh`. If you change the symlink to a binary that is not `/bin/zsh`, `/bin/bash` or `/bin/dash` - `/bin/sh` will default to running `/bin/bash`, and there are no easy tricks (like race conditions) that could be abused. I then thought that maybe Apple forgot to harden `/bin/dash` (because I saw the `zsh` and `bash` sources), but that's not the case - `dash` is also hardened.

## Using LLMs for the task
I automated downloading, extracting and assessing all pre/post install scripts, and used [Claude Code](https://code.claude.com/docs/en/overview) to do so. It offered several leads, and I asked it to research further and try to exploit each of them.  
Interestingly, out of 9 issues it found, it gave up on 7, and left 2 which I looked at personally and found to be useless.  
I decided that I personally wanted to take a closer look at the 7 Claude claimed could not be exploited, and looked at the package `Safari26.3.1SequoiaAuto.pkg` (sha1 = 20e778de14dba85790cc663983d241caa2429f6f), specifically the script `Scripts/postinstall_actions/loadSafariBookmarksSyncAgent`:

```perl
#!/usr/bin/perl
use strict;
use warnings;

my @users = `who |grep "console" | cut -d " " -f 1`;
my $pathToSafariBookmarksSyncAgentPlist = '/System/Library/LaunchAgents/com.apple.SafariBookmarksSyncAgent.plist';

foreach my $user (@users) {
    chomp($user);
    my $uid = `id -u  $user`;
    chomp($uid);
    system("launchctl asuser $uid launchctl kill 9 gui/$uid/com.apple.SafariBookmarksSyncAgent");
    system("launchctl asuser $uid launchctl unload $pathToSafariBookmarksSyncAgentPlist");
    system("launchctl asuser $uid launchctl load $pathToSafariBookmarksSyncAgentPlist");
}
```

Claude realized there is a command injection opportunity here if the output of `who` has shell-escaping characters such as backticks, but since users on macOS can only be alphanumeric (with underscores and other uninteresting characters) - it could not be done.  
I tried and indeed - `dscl` (nor the GUI) won't let me create usernames with backticks. Maybe in LDAP-controlled environment it could be done - but I did not have the environment to do so.  
I decided then to see if I could affect the `who` utility in a different way - if the `who` utility indeed examines the users, I'd expect it to import `DirectoryService.framework`. Here's a comparison between `who` and `dscl`:

```
jbo@JBOs-MacBook-Pro ~ % otool -L $(which dscl)
/usr/bin/dscl:
	/System/Library/Frameworks/Foundation.framework/Versions/C/Foundation (compatibility version 300.0.0, current version 4423.1.0)
	/System/Library/Frameworks/DirectoryService.framework/Versions/A/DirectoryService (compatibility version 1.0.0, current version 1.0.0)
	/usr/lib/libedit.3.dylib (compatibility version 2.0.0, current version 3.0.0)
	/usr/lib/libobjc.A.dylib (compatibility version 1.0.0, current version 228.0.0)
	/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1356.0.0)
	/System/Library/Frameworks/CoreFoundation.framework/Versions/A/CoreFoundation (compatibility version 150.0.0, current version 4423.1.0)
jbo@JBOs-MacBook-Pro ~ % otool -L $(which who)
/usr/bin/who:
	/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1356.0.0)
```

You can see how `dscl` imports `DirectoryService`, but `who` only uses `libSystem`, which I find suspicious.  
I decided to take a closer look, and `who` apparently uses an API called [getutxent](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/getutxent.3.html).  
Those are entries in an old UNIX relic of a "login accounting system" which is known as [utmp](https://en.wikipedia.org/wiki/Utmp).  
More interestingly, those records are saved in a file `/var/run/utmpx` which is not SIP protected!  
That means I can write to the file, change the console (interactive) user to have backticks and be done with it.
