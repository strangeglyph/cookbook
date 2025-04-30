{
  description = "Cookbook overlay";

  outputs = inputs: {
    overlay = final: prev: {
      cookbook = final.callPackage ./derivation.nix {};
    };
  };
}
