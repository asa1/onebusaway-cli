{ pkgs ? import <nixpkgs> {}}:

pkgs.mkShell {
  buildInputs = [
    pkgs.python311Packages.blessings
    pkgs.python311Packages.requests
  ];
}
