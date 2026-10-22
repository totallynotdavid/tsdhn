# Release

The `Release` workflow, [`release.yml`](../.github/workflows/release.yml),
builds the wheels, the model bundle and the five container images. It publishes
them when you push a tag that matches `v*.*.*`.

## Cut a release

1. Set the version in `packages/tsdhn/pyproject.toml`.
2. Make the first line of `.github/release-notes.md` read
   `tsdhn <version> is out.` The rest of the file is the release body.
3. Merge the change. The workflow runs on the pull request first (see
   [Dry run](#dry-run)).
4. Tag the merge commit and push the tag:

   ```sh
   git tag v<version>
   git push origin v<version>
   ```

The tag run fails at once if the tag differs from the package version or the
notes name another version.

## Dry run

A manual run (`workflow_dispatch`) runs the whole workflow without a tag. It
builds the same artifacts and checks every upload that has a dry-run mode. It
skips only the steps that publish and have none: the image promotion, the PyPI
upload and the GitHub release. Those steps name the tag ref in their `if:`.

A pull request always runs the cheap jobs. It runs the image jobs, the smoke
test and the promotion check only when it changes an image input, or the release
notes, which makes it a release pull request. The list of inputs is
`IMAGE_INPUTS` in [`changes.py`](../scripts/ci/changes.py). The
[CI table](testing.md#ci) shows which job runs on which change.

| Job                     | What the dry run proves                                      |
| ----------------------- | ------------------------------------------------------------ |
| `changes`               | Which jobs this run needs.                                   |
| `preflight`             | The `pypi` environment exists when PyPI publishing is on.    |
| `build-sdist-wheels`    | The notes match the package version. `uv publish --dry-run`. |
| `build-model-assets`    | The model bundle builds.                                     |
| `build-toolchain-image` | The toolchain image builds and its tools run.                |
| `build-app-images`      | The API, web, backup and development images build.           |
| `compose-smoke`         | The candidate images start and pass the smoke test.          |
| `promote-images`        | Every candidate image exists in the registry.                |
| `release-notes`         | The notes file and the model bundle are present.             |
| `warm-image-cache`      | Nothing. It fills the build cache after a push to master.    |

The image jobs push candidate images, tagged `candidate-<run id>`, because jobs
on other runners pull them. The tag has no attempt number: a rerun of the failed
jobs finds the images the first attempt pushed, and a full rerun overwrites
them. A pull request from a fork cannot push, so it builds no images, as if it
changed no image input.

## Image build cache

A build cache written on a pull request is visible to that branch alone. Other
branches read the default branch's cache. So only a push to master writes it:
when the push changes an image input, `warm-image-cache` rebuilds the five
images on a local registry and fills the cache. It pushes no image to GHCR and
promotes none. Pull requests, manual runs and tag runs read the cache and do not
write it.

The api and development images start from the toolchain image, and their cache
follows its digest. A buildx attestation changes the digest of an identical
rebuild, so the toolchain image carries one only on a tag run.

## Publish to PyPI

The `publish-pypi` job is off until the repository variable `PUBLISH_PYPI` is
`true`. While it is off, `preflight` reports PyPI as skipped.

The job uses trusted publishing, so no token is stored. Set it up once:

1. On PyPI, open the `tsdhn` project, then Manage, Publishing. For a project
   that does not exist yet, open Your account, Publishing, and add a pending
   publisher.
2. Add a GitHub publisher with these values:
   - Owner: the GitHub account or organisation that owns the repository.
   - Repository name: the repository name.
   - Workflow name: `release.yml`.
   - Environment name: `pypi`.
3. In the GitHub repository, open Settings, Environments, and create an
   environment named `pypi`. Add protection rules if you want an approval before
   each upload.
4. Turn publishing on:

   ```sh
   gh variable set PUBLISH_PYPI --body true
   ```

Turn it off with `gh variable delete PUBLISH_PYPI`.
