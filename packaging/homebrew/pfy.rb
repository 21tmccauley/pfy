# Homebrew formula for pfy — the source of truth lives here; the release workflow
# (.github/workflows/release.yml) fills in the version + checksums and commits the
# rendered copy to the tap repo (paramify/homebrew-tap) as Formula/pfy.rb.
#
# Install:  brew install paramify/tap/pfy
#
# The bottle is a PyInstaller onefile binary with the interpreter and every
# dependency (incl. the private paramify-sdk) baked in — no Python, no auth on the
# device. It's arch-specific because pydantic-core ships a native wheel.
class Pfy < Formula
  desc "Paramify FDE CLI — porcelain workflows + plumbing primitives"
  homepage "https://github.com/paramify/pfy"
  version "VERSION_PLACEHOLDER"

  on_macos do
    on_arm do
      url "https://github.com/paramify/pfy/releases/download/vVERSION_PLACEHOLDER/pfy-macos-arm64.tar.gz"
      sha256 "SHA_ARM_PLACEHOLDER"
    end
    on_intel do
      url "https://github.com/paramify/pfy/releases/download/vVERSION_PLACEHOLDER/pfy-macos-x86_64.tar.gz"
      sha256 "SHA_INTEL_PLACEHOLDER"
    end
  end

  def install
    bin.install "pfy"
  end

  test do
    assert_match "Paramify FDE CLI", shell_output("#{bin}/pfy --help")
  end
end
