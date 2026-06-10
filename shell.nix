{ pkgs ? import <nixpkgs> {}}:

pkgs.mkShell {
  buildInputs = [
    pkgs.python314Packages.blessed
    pkgs.python314Packages.requests
  ];
}
