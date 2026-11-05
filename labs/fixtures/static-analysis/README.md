# Static-analysis inputs

Use these files only for [SC08](../../supply-chain.md#sc08-static-analysis). **Do not apply the Deployment or build/run the Dockerfile unchanged.** They are intentionally flawed scanner inputs, not deployment instructions.

Investigate mutable image identity, root execution, privilege escalation, filesystem writes, unnecessary token mounting, missing resource controls and an overly broad build context. Tool versions and enabled checks affect the findings; not every item is guaranteed to appear in a particular scanner's output.

Copy the files into `work/SC08/`, repair a separate copy, and keep reports outside the scanned/build directories. The original files contain no credentials, host mounts, privileged containers or publicly exposed Service. Removing scanner findings does not prove that a workload is functional or that every security requirement is met.
