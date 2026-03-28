# UTMPWN
In March 2026, I've decided to look for a new SIP bypasses.  
I've written about SIP [in a previous blogpost](https://github.com/yo-yo-yo-jbo/macos_sip/) and myself have contributed some bypasses over the years.

## SIP bypasses I have reported in the past
To give some context, here are SIP bypasses I have reported in the past:

### Shrootless - CVE-2021-30892
[CVE-2021-30892 (AKA "Shrootless")](https://www.microsoft.com/en-us/security/blog/2021/10/28/microsoft-finds-new-macos-vulnerability-shrootless-that-could-bypass-system-integrity-protection/) was a PackageKit issue in `system_installd`.  

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
