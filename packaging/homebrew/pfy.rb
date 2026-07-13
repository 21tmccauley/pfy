# Homebrew formula for pfy — the source of truth lives here; the release workflow
# (.github/workflows/release.yml) fills in the version + checksums and commits the
# rendered copy to the tap repo (21tmccauley/homebrew-tap) as Formula/pfy.rb.
#
# Install:  brew install 21tmccauley/tap/pfy
#
# The bottle is a PyInstaller onedir bundle with the interpreter and every
# dependency (incl. the private paramify-sdk) baked in — no Python, no auth on the
# device. It's arch-specific because pydantic-core ships a native wheel. onedir
# (not onefile) so startup doesn't pay a re-extract + Gatekeeper re-scan each run.
class Pfy < Formula
  desc "Paramify FDE CLI — porcelain workflows + plumbing primitives"
  homepage "https://github.com/21tmccauley/pfy"
  version "VERSION_PLACEHOLDER"

  # arm64 only — GitHub retired the Intel macOS runners, so no x86_64 bottle is
  # built. Add an on_intel branch back here (with its build + sha) if that changes.
  on_macos do
    on_arm do
      url "https://github.com/21tmccauley/pfy/releases/download/vVERSION_PLACEHOLDER/pfy-macos-arm64.tar.gz"
      sha256 "SHA_ARM_PLACEHOLDER"
    end
  end

  # onedir bundle: the executable needs its sibling _internal/ dir, so install the
  # whole thing into libexec and expose just the launcher on PATH via a symlink.
  def install
    libexec.install Dir["*"]
    bin.install_symlink libexec/"pfy" => "pfy"
  end

  test do
    assert_match "Paramify FDE CLI", shell_output("#{bin}/pfy --help")
  end
end
