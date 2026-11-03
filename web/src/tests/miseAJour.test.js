import { beforeEach, describe, expect, it, vi } from "vitest";
import { rechargerApresMiseAJour } from "../miseAJour.js";

const evenement = () => ({ preventDefault: vi.fn() });

describe("rechargement après une mise à jour du site", () => {
  beforeEach(() => sessionStorage.clear());

  it("recharge la page quand un ancien fichier manque", () => {
    const e = evenement();
    const recharger = vi.fn();
    rechargerApresMiseAJour(e, 1_000_000, recharger);
    expect(recharger).toHaveBeenCalledOnce();
    expect(e.preventDefault).toHaveBeenCalled();
  });

  it("ne boucle pas : une seule fois par minute, ensuite l'erreur suit son cours", () => {
    rechargerApresMiseAJour(evenement(), 1_000_000, vi.fn());
    const e = evenement();
    const recharger = vi.fn();
    rechargerApresMiseAJour(e, 1_030_000, recharger);
    expect(recharger).not.toHaveBeenCalled();
    expect(e.preventDefault).not.toHaveBeenCalled();
    rechargerApresMiseAJour(evenement(), 1_070_000, recharger);
    expect(recharger).toHaveBeenCalledOnce();
  });
});
