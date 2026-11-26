# RGPD-1 : identifiants devinables et limitation des tentatives de connexion (#87)

<!-- Issue #87 — Retirer le nom des enfants : identifiant prénom + numéro (Claude) -->

> Revérification demandée par #87, 15/11/2026, code de `develop` après la migration `0039`.
> Aucune donnée réelle n'est utilisée : tests automatisés seulement.

## 1. Ce qui change

| | Avant RGPD-1 | Après RGPD-1 |
|---|---|---|
| Identifiant | `lina-k7m4` : prénom + 4 caractères aléatoires (31⁴ ≈ 923 000 possibilités par prénom) | `Lina1`, `Lina2`… : prénom + numéro **séquentiel** |
| Deviner un identifiant existant | pratiquement impossible sans la carte | **facile** : prénoms courants et petits numéros |
| Seul secret | le code personnel | le code personnel (6 caractères parmi 31 : 31⁶ ≈ 887 millions) |

Les identifiants ne sont pas des secrets : ils sont imprimés sur les cartes et affichés aux adultes. Le code
personnel reste la seule protection, d'où cette revérification.

## 2. Limites en place (`app/limitation.py`, `app/config.py`), fenêtre de 15 minutes

| Limiteur | Clé | Plafond | Effet sur le balayage d'identifiants devinables |
|---|---|---|---|
| `echecs_code_eleve` | compte (`carte:<identifiant>`) | 5 échecs | bloque **un** compte, quelle que soit l'adresse |
| `codes_inconnus` | adresse IP | 30 identifiants **inexistants** | **ne joue plus** : les identifiants essayés existent |
| `par_ip` | adresse IP | 300 tentatives | **seul frein** à l'essai d'un même code sur de nombreux comptes |

Contrôlé par des tests (`api/tests/test_identifiants_rgpd1.py`) :
- `test_meme_reponse_que_l_identifiant_existe_ou_non` : même code HTTP (401) et même message, que l'identifiant
  existe ou non. La durée est constante : une empreinte leurre est vérifiée quand le compte n'existe pas (`_code_leurre`).
- `test_un_code_essaye_sur_des_identifiants_devinables_est_freine_par_adresse` : un même code essayé sur 70
  identifiants « LinaN » depuis une adresse. Les 300 premiers essais reçoivent 401, le 301ᵉ reçoit 429 (`par_ip`).
  Un compte est bloqué après 5 échecs (`echecs_code_eleve`).

## 3. Évaluation

Un attaquant qui essaie des codes au hasard sur des identifiants devinables obtient, **par adresse IP** :
300 essais / 15 min, soit environ 10,5 millions d'essais par an. Chaque essai a une chance sur 887 millions de tomber juste.
Cela fait **environ 1,2 % par an et par adresse** de trouver le code d'un compte, quel qu'il soit. Le risque croît avec le nombre d'adresses
(réseau de machines) : la limite par compte (5 essais) ne suffit pas, puisque l'attaquant change de compte à
chaque essai.

Avant RGPD-1, il fallait d'abord trouver un identifiant existant. `codes_inconnus` (30 identifiants inexistants par
adresse) rendait ce balayage inefficace.

## 4. Proposition et décision **SEC-D5**

1. **Limite par adresse sur les échecs** de connexion par carte : `echecs_carte_par_ip` = **60 échecs / 15 min**,
   en plus des 300 tentatives. Une classe de 35 élèves derrière la même adresse (réseau d'établissement) garde de la
   marge pour les fautes de frappe. Effet : environ 0,24 % par an et par adresse, cinq fois moins.
2. **Surveillance** : compter les échecs de connexion par carte, toutes adresses confondues, et les signaler dans le
   journal au-delà d'un seuil (par exemple 1 000 par heure), pour repérer un balayage réparti.
3. Plus tard, si le besoin se confirme : allonger le code personnel des nouvelles cartes à 7 caractères
   (31⁷ ≈ 27 milliards, trente fois plus), sans toucher aux cartes déjà distribuées.

**Décision du propriétaire (15/11/2026)** : le point 1 est **appliqué** (`limitation.echecs_eleve_par_ip`, réglage
`PKP_CONNEXION_ELEVE_MAX_ECHECS_PAR_IP`, défaut 60). Il vaut pour toutes les connexions élève : carte d'enfant,
identifiant, prénom + code classe et anglais. Les points 2 et 3 ne sont pas retenus à ce stade.

Contrôlé par `test_un_code_essaye_sur_des_identifiants_devinables_est_freine_par_adresse` : au 61ᵉ échec, l'adresse
reçoit 429, y compris par une autre route de connexion élève. `test_une_classe_derriere_une_meme_adresse_n_est_pas_bloquee`
vérifie que 35 élèves derrière une même adresse, avec dix fautes de frappe, se connectent tous.
