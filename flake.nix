{
  description = "Cookbook overlay";
  
  inputs.nixpkgs = { url = "github:nixos/nixpkgs/nixos-25.11"; };

  outputs = inputs: {
    overlay = final: prev: {
      cookbook = final.callPackage ./derivation.nix {};
    };
    package = (import inputs.nixpkgs { system = "x86_64-linux"; }).callPackage ./derivation.nix {};
  };
}
