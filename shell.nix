{ pkgs ? import <nixpkgs> {}}:

pkgs.mkShell {
  buildInputs = [
    pkgs.python311Packages.blessed
    pkgs.python311Packages.requests
  ];
}
