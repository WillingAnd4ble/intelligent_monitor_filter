## **1. Įvadas** 

The appearance of Transformers and creation of Large Language models on top of it opened huge opportunity to utilize tools that are capable of doing text summarization, semantic understanding, classification and output seemingly reasonable text. Those capabilities let into creation of LLM-based agents, entities that can perform more complex tasks with reasoning, planning and acting. The design of single-agent systems aims to perform specific tasks, ranging from simple automation to complex decision making. (Li et al., 2024) Whereas multi-agent systems aim to communicate with each other and find the solution for big and complex task. There is not many cases where the agentic systems are applicable yet. A lot of companies and researchers try to experiment and find the use-cases that can be solved or be augmented with such systems. 

One of prominent cases is information filtering and relevant information discovery. Moreover the LLM-based or Agentic recommender systems are underexplored as well as proactive architectures remain unnoticed. Given the semantic understanding of LLMs there is seemingly large potential in filtering content and personalizing it to the user. One such application can be relevant article filtering or job-listing, study material, listing and commerce filtering given specified goals, preferences or explaining whole specification what is needed. That can augment better discovering fighting the overhelming number of   new information appearing in dynamic sources. 

Current recommenders are collaboratively driven, they aren’t focused on specific users but groups, where mixed recommendation architectures utilize other capabilities of AI domain like Machine learning, autoencoders or transformers. Another domain of finding relevant information is the search, its capabilities are limited whereas they are used as reactive engines, where user needs to type in what is needed and the information is retrieved utilizing keyword matching and other vector space matching techniques. 

In this work the idea of using LLM as recommender and filtering system is explored. By creating a simple single-agent LLM and more complex multi-agent LLM system for personal recommendations engine. Finding out whether these systems are sufficient for recommending given the specific goal and specification in simple words if there is specified what is needed and whether the complexity of the system is needed or decomposition of the specifying the tasks. Where the evaluation domains are scientific papers from arXiv cs.AI and job listings is the practical feature of the system. 

6 

**Tyrimo problema** – LLM-based agents have shown the effectiveness with understanding the text material, but they are most used as reactive and single-query tools. The proactive application of content-filtering is underexplored. The work is addressing the engineering challenge of building a agent systems that autonomously monitor, evaluate and filter continuously updating content streams aligned with user-defined objectives and comparing two architectures. 

**Tyrimo objektas** – Agentic systems in application for content-based filtering. 

**Tyrimo tikslas** – Design, implement and evaluate a multi-agent LLM-based system for proactive content filtering and validate it in the domain of scientific publications monitoring. 

## **Tasks to accomplish goal** : 

1. Analyze existing architectures and identify patterns that are applicable to proactive filtering. 

2. Design and implement a …. 

3. Evaluate system filtering precision, agent coordination efficiency on daily arXiv paper monitoring. 

## **Research methodology:** 

Literature review, system design and implementation, experimental testing, quantitative evaluation (extraction quality, price), prototype demonstration were picked as research methods. 

7 

## **2. Literatūros apžvalga** 

## **2.1. Informacijos perkrova** 

Spartėjant mokslinei pažangai, mokslinės literatūros ir naujos informacijos kiekis auga be precedentinių greičiu, o tai tampa dideliu iššūkiu ne tik tyrėjams, medikams bet ir kitų profesijų atstovams reikalaujantiems būti aktualių ir žinoti kas vykstą jų specifinėje srityje. Žurnale „Nature“ patalpintame straipsnyje (Lutz Bornmann ir kiti, 2021) parodoma kad bendras metinis augimo lygis yra 4.10% ir nusakoma kad per 17.3 metų apimtis padvigubės. Kitas nuolatinės pažangos aspektas yra tai, kad žinios turi tam tikrą gyvavimo ciklą, trukmė po kurios žinios nėra aktualus ir šis laikas yra žymiai sutrumpėjąs. Konkrečiau, būti inžinieriumi reiškia, kad tam tikru momentu tam tikrą informacija taps pasenusi. Esami įvertinimai rodo, kad 1960 m. žinios paseno per 10 metų, o šiuo metu šis skaičius yra daug mažesnis. Roberto N. Charette 2013 straipsnyje IEEE žurnale nuspėjama kad tas skaičius yra nuo 3 iki 7  metų priklausomai nuo srities, praėjus laikui galima sakyti kad šis skaičius yra dar mažesnis, kadangi straipsnis buvo patalpintas 2013 metais. Verslo plėtros pobūdis reikalauja neatsilikti nuo naujausių ir geriausių įvairių problemų sprendimų, o šiuo atveju informacijos perteklius reiškia tiesioginę problemą, kuri žymiai mažina produktyvumą ir slopina kūrybiškumą. Informacijos perteklius  tiesiogiai prisideda prie ekonominių nuostolių, kurie kasmet visame pasaulyje siekia 650 mlrd. JAV dolerių, ir sukuria situaciją, kai „informacijos gausa sukelia dėmesio trūkumą ir būtinybę efektyviai paskirstyti tą dėmesį“. [3](Roetzel, Gordon, 2019) Vienas iš nusistovėjusiu požiūrių į susidorojimą su informacijos perteklių pagal paminėta publikaciją yra sisteminė literatūros apžvalgą, bet šis būdas reikalauja sisteminio požiūrio ir pastovaus darbo ties vienos tematikos. Šis būdas, kuris aktualus medikams ir tyrėjams, laikoma aukščiausiu standartu, bet tai nėra aktualų kitoms profesijos atstovams, kurie neturi galimybės skirti tam didelį laiko ir dėmesio kiekio. Taip pat, neatmetama, kad informacija ir žinios greitai vystosi, tad toks didelis darbas gali greitai pasensti. Greitai besikeičiančių sričių, pavyzdžiui, dirbtinio intelekto inžineriai dažnai grėbiasi neformalių strategijų, kaip autorių sekimas socialiniuose tinkluose arba žiniasklaidoje, naudojimąsi konferencijų galimybėmis arba tiesiogiai remiasi žodine informacija, tai nusako, kad naujos sritys yra sunkiai aprėpiamos ir reikalaujama naujų būdų sisteminio informacijos gavimo. Būtent kitas būdas apžvelgtas tame pačiame straipsnyje [3] pabrėžia, kad būtina sukurti naujas sistemiškos apžvalgos sistemas ir akcentuojama kad reikalinga automizuota stebėjimo sistemą ir būtent šį idėja tapo motyvacija šiam darbui. 

## **2.2. Informacijos ir informacijos grąžinimo sistemos** 

Several research fields are related to user modeling and (research-paper) recommender systems. Although we do not survey these fields, we introduce them so interested readers can broaden their research. Research on academic search engines deals with calcu lating relevance between research papers and search queries [227–229]. The techniques are often similar to those used by research-paper recommender systems. In some cases, rec ommender systems and academic search engines are even identical. As described later, some recommender systems require their users to provide keywords that represent their interests. In these cases, research-paper recommender sys tems do not differ from academic search engines where users 

8 

provide keywords to retrieve relevant papers. Conse quently, these fields are highly related and most approaches for academic search engines are relevant for research-paper recommender systems. (Beel et al., 2015) 

Informacijos perkrovos problematika nėra naują. Tai jau buvo aktualų per daugelis dešimtmečiu. Išsivysčius internetui ir reaguojant į informacijos perteklių atsirado informacijos paieškos sritis. (angl. Information Retrieval) Iš kurios pasėkoje atsirado paieškos algoritmai ir varikliai. Ši sritys yra aktuali šiam darbui, nes tai yra procesas, kurio metu iš didelės duomenų bazės randama reikalinga informacija su tikslu patenkinti vartuotojo poreikį. [4] (Zhang W ir kiti, 2025) Anksčiausios sistemos rėmėsi Būlio (angl. Boolean) paieškos modeliais, kur vartotojai darė užklausas iš loginių operatorių (AND, OR, NOT), bandant atitikti dokumentus, kuriuose yra tikslios raktažodžių kombinacijos. Šis būdas buvo labai nelankstus, nes dokumentas arba atitikdavo užklausą arba ne. Didžiulis žingsnis į priekį buvo VSM modelio sukūrimas.(Salton et al., 1975) Pagrindinė šio darbo idėja buvo tame, kad dokumentus galima reprezentuoti vektorinėje erdvėje, kur kiekvienas raktažodis tai atskira dimensija, o dokumentų panašumas apibrėžiamas kampų tarp jų vektorių. Kuo mažesnis kampas, tuo dokumentai labiau panašūs. Tai leido reitinguoti ir surūšiuoti grąžinamus dokumentus pagal atitikimo laipsnius duotai užklausai. Šis modelis tapo pamatų šiuolaikinėse informacijos paieškose. Taip pat, šiame darbe buvo paminėtas TF-IDF, plačiai DI ir NLP srityje naudojamas, pritaikymas. Kurios pagrindinė idėja yra tą kad žodžio dažnumas dokumente (TF) ir retumas visame žodžių rinkinyje (IDF) apibrėžia jo svarbą. Ši idėja taip pat, turi didžiulė įtaką šių dienų technologijoms. Paminėti dalykai greičiausiai neprisidės prie galutinio sprendimo, bet jie gali tapti testavimo pamatu. Dar verta paminėti BM25 reitingavimo funkcija (Robertson & Zaragoza, 2009), kurį iki šiol yra plačiai naudojama kaip pradinis taškas paieškos sistemose. Šios technikos turi savo pranašumą leksikos supratime, bet turi ir trūkumų, pavyzdžiui, žodyno neatitikimo, kai vartotojo užklausos neatitinka dokumentų arba vartotojas naudoja sinoniminius žodžius. Taip pat, šie metodai neturi semantinio supratimo. 

Giliųjų neuroninių tinklų ir transformerių atsiradimas atnešė naujų būdų ir pokytį informacijos paieškoje. Karpuhin ir kt. 2020 pristatė tankiojo ištraukos grąžinimo modelį (angl. Dense Passage Retrieval, DPR). Tai yra dvigubo kodavimo sistemą arba kitaip tariant naudojama du BERT enkodoriai, užkoduojantys užklausą ir dokumentus į tankiuosius vektorinius atvaizdavimus dar vadinamus angl. „embeddings“, kurie išmoksta semantines reprezentacijas. Dokumentų atitikimą užklausai vertinamas skaičiuojant abiejų vektorių skaliarinę sandaugą, o modelis mokomas maksimizuoti panašumą tarp tinkamų užklausos ir dokumento porų. Šis modelis pranoko LuceneBM25 9-19 procentų didesnių tikslumų 20 geriausių paieškos atveju sugrąžinimui. Modelis parodė gebėjimą suderinti semantiškai susijusias sąvokas (pavyzdžiui, „blogas“ ir „piktadarys“) be leksinio sutapimo. (Karpukhin et al., 2020) Taip pat, darbe Emergent Mind Noguera ir Cho (2019) buvo parodyta, kad BERT pagrįstas kryžminio kodavimo (angl. cross-encoder) perrinkimas (angl. re- 

9 

ranking) gali dar labiau padidinti tikslumą lyginant su MS MARCO testu. (Nogueira & Cho, 2019) Tai davė pradžią šiuolaikiniam dviejų etapų grąžinimo (angl. retrieval) procesui: greitas pirmojo etapo atgavimas generuojantis pirmą kandidatų sąrašą ir sekantis reikalaujantis resursų, bet tikslus neuroninis perrinkėjas (angl. re-ranker). 

Šiuolaikiniai informacijos paieškos sprendimai tobulėja, bet su ateinančia pažangą galima pastebėti, kad tyrėjai bando ir mėgina pridėti naujausias technologijas, net ir jau nusistovėjusiai sričiai. Patobulėjant transformeriams ir atsiradus didžiosios kalbos modeliams atsiveria dar naujesnis šios srities horizontas. Galima teigti, kad paieškos sistemos iš esmės lieka reaktyvus, tai yra vartotojas turi suformuluoti užklausą ir pradėti paiešką. Ši paradigma remiasi prielaida, kad vartotojas žino, ko ir kada ieškoti. Tyrėjas, norintis būti informuotas apie naujas publikacijas savo srityje, o to labiau tikslioje tematikoje su tam tikru kampu turi kasdien tikrinti platformas ir rankiniu būdu peržiūrėti šimtus pavadinimų ir viršelių arba sudaryti užklausas, kurios neišvengiamai praleis straipsnius kuriuose naudojama kitokia terminologija. Žiūrint plačiau tokių temų ir sričių gali būti daugelis, tad neišvengiamai toks uždavinys yra sunkus ir reikalaujantis daug laiko, nes esamos sistemos dažniausiai reikalauja to aktyvaus naršymo ir ieškojimo. Šį atotrūkį bando išspręsti rekomendacinės sistemos. [might add something from ] 

latent semantic analysis (LSA)? 

## **2.3. Dabartinė mokslinės literatūros rekomendacinių sistemų būklė** 

Rekomendacinės sistemos atsirado su panašiu tikslų - pateikti vartotojui informacija, kuri gali būti jam aktuali. Taip pat šios sistemos atlieka panašia funkciją, kaip tradicinė informacijos paiešką, surasti ir pateikti informaciją iš didelio duomenų rinkinio, bet pagrindinis skirtumas yra tame, kad jos siekia nuspėti, kokia informacija vartotojui bus naudinga arba aktuali. Nuspėjimo principai remiasi vartotojo ankstesne elgsena, amžiumi, lytimi, kilme ir buvimo lokacija, idealiu atveju pomėgiais jeigu žmogus praveda pakankamai laiko platformoje, taip pat technologijoms vystant atsiranda platformų su papildomais požymiais, kaip rekomendavimas pagal nuotaiką. Nuspėjimo principai skirstomi į dvi pagrindines kategorijas: kolaboratyvųjį (angl. Collaborative filtering, CF) ir turini pagristą filtravimą 

10 

- (angl. Content-based filtering, CBF). Produkcinėse sistemose arba industrijoje dažniausiai 

**Error! No text of specified style in document.** .1 pav 

pav. **Error! No text of specified style in document.** .2 

. pav(šalt.) 

naudojamos hibridinės sistemos apjungiantys jas kartu. 

Remiantis publikaciją iš žurnalo „Springer Nature Neural Computing and Applications“ pavadinimu „Revisiting recommender systems: an investigative survey“ (Ali et al., n.d.) kolaboratyvusis filtravimas yra plačiausiai naudojama metodika rekomenduojant tokiu principu, jeigu du vartotojai turėjo panašius preferencijas praeityje, tai greičiausiai jas turės panašias ateityje. Pabrėžiant veikimo idėja, galima matyti, kad šis būdas gali būti neefektyviai veikiantys filtravime pagal naudotojo apibrėžtą tikslą mokslo straipsnių kontekste ir sistemoje, kur personalizavimas pagal vartotoja yra svarbesnis, nei filtravimas pagal populiacijos grupės. Mokslo straipsnių srityje, temos ir vartotojo poreikis gali varijuotis per plačiai. Taip pat žinant, kad nusakoma vartotojų bazė, nėra pernelyg didelė, dėl siauro poreikio. Šis būdas efektyviausiai veikia sistemose, kur nusakoma vartotojų bazė yra labai didėle. Analizuojant giliau veikimo principus galima skirstyti šį būda į du atskiras technikas: atminities arba kaimino pagrįsta (angl. Memory-based) ir modeliu pagrįsta (angl. Model-based). Atminties pagrįstoje technikoje rekomendacijos priklauso nuo vartotojo artumo jo kaimynams, tai yra, panašiems vartotojams. Panašiu būdu, kaip buvo paminėta 2.2 paragrafe, tik tai skaičiavimai atliekami Pearsono koreliacijomis arba kosinuso panašumu. Svarbu paminėti, kad artumas gali būti skaičiuojamas ir elementui arba objektui, kurį norima rekomenduoti. Kita metodologija, modeliu pagrįsta, pasitelkia mašininio mokymo naudojimu, kur vyksta modelio apmokymas istorinėmis duomenimis. Svarbiausia šios srities metodas yra Matricos  faktorizavimas (angl. Matrix factorisation), kuris yra panašus į jau minėta vektorių erdvės modelį (VSM). Šiuo 

11 

metodu kiekvienas vartotojas yra atstovaujamas vektoriumi, sudarytu iš jo vertinimų rekomendacijų sistemoje, pavyzdžiui, esančioms prekėms, o kiekviena prekė yra atstovaujama vektoriumi, sudarytu iš kitų vartotojo vertinimų. Tam atliekamas matricos faktorizavimas, kuris apima matmenų arba dimensijos sumažinimą, skaidant į vartotojo-elemento matricą. Tai pasiekiama formuojant linijinę lygtį, apibūdinančią santykį tarp vidutinių vartotojo įvertinimų, bei vartotojo ir elemento šališkumo. Ši lygtis yra naudojama išgauti numatomiems elementų arba vartotojų įvertinimams.  Vertingiausias dalykas iš šio metodo yra SVD, kuris leidžia rekomenduoti realiu laiku. (Ali et al., n.d.) 

- (Žinomas CB rekomendacijų sistemų trūkumas yra „filtro burbulo“ efektas (Portenoy et al., 2022), o įvairovė, naujumas ir atsitiktinumas buvo įvardyti kaip dabartiniai trūkumai (Kreutz ir Schenkel, 2022; Ali et al., 2021; Bai et al., 2019; Nguyen et al., 2014). Priešingai, bendradarbiavimo filtravimas (CF) rekomendacijas gauna iš daugelio vartotojų interesų, o dabartiniai metodai skiriasi tuo, ar jie naudoja autoriaus informaciją (Utama ir kt., 2023; Neethukrishnan ir Swaraj, 2017), sąveikas (Murali ir kt., 2019; Xia ir kt., 2014) ar bibliografinę informaciją (Sakib ir kt., 2020; Haruna ir kt., 2017; Liu ir kt., 2015). Naujausi tyrimai sutelkia dėmesį į hibridines sistemas, įtraukiančias CB ir CF į dviejų bokštų architektūras (Church et al., 2024; Yi et al., 2019) arba grafais pagrįstus metodus (Wang et al., 2024; Ostendorff et al., 2022; Cohan et al., 2020). CB, CF ir hibridiniai metodai visi susiduria su rekomendacinių sistemų „šalto starto“ problema, nes rekomendavimo sistema nežino vartotojo preferencijų, kai jis pradeda naudoti sistemą (Bai ir kt., 2019). Buvo daug bandymų šią problemą sušvelninti (Nura ir Hamisu, 2024), pavyzdžiui, įkeliant BibTeX failus iš nuorodų tvarkyklės (Kart ir kt., 2022). „Scholar Inbox“ švelnina „šalto starto“ problemą naudotojui patogiu įvedimo procesu ir aktyvios mokymosi strategija. 

)  scholar inbox worth it. 

Kažkur čia parašyti apie cold-start problemą. [2.3 Coldstart problem The cold start problem happens when there is insufficient data about new users or items, making it difficult to gener ate accurate recommendations. This typically occurs when a user has just joined the platform or when new products are added to the catalog without prior interactions. As a result, recommendation models have to struggle to identify mean ingful patterns due to the lack of historical feedback. The cold start issue significantly reduces recommendation qual ity and user satisfaction, especially in early-stage systems or rapidly evolving domains. Addressing the cold start prob lem often requires employing auxiliary information such as user demographics, item metadata or hybrid recommenda tion strategies.] (Wang et al. (2026)) [ **Meta-path attention with semantic transformer for academic recommendation** ]  tbh best source to describe those systems with this author( In summary, paper recommendation methods can be broadly classified into three categories: CBF, CF and GB. CBF rec 

12 

ommends papers with attributes similar to those that a user has liked, focusing on the intrinsic features of the papers. By extracting keywords, titles, abstracts and other features, CBFevaluates the similarity between papers to improve rec ommendation personalization. CF measures similarity based on collective user feedback, predicting user preferences by identifying similar users or papers. However, both CBF and CF face challenges such as the cold start problem and data sparsity. As a result, the adoption of GB methods has been growing in recent years. GB methods construct graphs based on various rela tionships between papers, enabling a more comprehensive capture of complex interconnections among them. This is primarily facilitated by the introduction of GAT by Velick ovic et al. [2], which overcome limitations of traditional graph convolutional networks (GCNs), such as the ability to assign dynamic weights based on the features of neighbor ing nodes. However, existing graph-based recommendation methods often neglect the temporal sequence of user prefer ences.) 

TOBE HONEST THIS WORK ALSO BRILLIANT (Bai et al., 2020) Scientific Paper Recommendation: A Survey 

Turinio pagrįstos rekomendacinės sistemos iš esmės remiasi vartotojo arba elemento aprašomosiomis savybėmis (Musto et al., 2022), užuot vartotojų įverčių naudojimo ir jų atitikimo panašioms naudotojų grupei. Galima teigti, kad šis būdas koncentruojasi ties pačio turinio, bei vartotojo bruožus. Pagal tuos pačius autorius, šis metodas naudojamas rekomendacijoms susietoms tiek su elementais, kurie pateikiami su tekstiniu aprašymu, pavyzdžiui, filmo siužetas, tiek su elementais, kurie patys yra tekstiniai, kaip šiam darbui aktualiems moksliniams straipsniams. Būdingai šios sistemos rekomendacijos išgaunamos suderinant vartotojo profilius su elementais. Vartotojo kurie dažniausiai turi informaciją apie pomėgius, interesus ir kitus atributus kurie galėtu atvaizduoti platesnį vaizdą apie jį. Taip pat tai gali vykti ir su elementais, kurie turi platesnius aprašymus, atskleidžiančius ypatybes. Ankstyvieji turinio pagrįsti modeliai buvo paprasti ir naudojo paprastus terminus ir raktažodžius (Musto et al., 2022), todėl atitinkamai dėl technologinių apribojimų moksliniai tyrimai susitelkė labiau prie bendradarbiavimo metodo. Problemos? 

Mokslinių straipsnių filtravimo kontekste šie pagrindiniai aukščiausio lygio būdai susiduria su specifiniais iššūkiais. Beel ir kt. (2015) atliko išsamų mokslinį straipsnių tyrimą skirtam mokslinių darbų rekomendavimui, kuriame autoriai pražvelgė 200 tyrimo straipsniu už pastarąsias 16 metų nuo publikavimo periodo. Buvo atrasta, kad 55% rekomendavimo būdu pagrinde veikė su turinio pagrįstu metodu. Galima teigti, kad tuo metų situacija buvo mokslinių straipsnių filtravimas turėjo išskirtinė situacija, nes dauguma rekomendavimo sistemų fokusavosi labiau į bendradarbiavimo architektūras. Autorių darbe nusakoma kad šis kiekis buvo tokių būdu rekomendacijos buvo atliekamos tik 18% ir 16% grafų pagrįstais. Taip pat darbe pabrėžiama, kad turiniui filtruoti dažniausiai buvo naudojamas TF-IDF. Kitas nusakomas pabrėžiamas aspektas, kad nebuvo vaizdžiai matoma, kuris būdas iš tikrųjų 

13 

yra geriausias ir autoriai paminėjo, kad ši specifinė sritis neturėjo didėlio mokslininkų susidomėjimą. Buvo atliktas naujesnis tyrimas Kreutz & Schenkel (2022) siekiantis išanalizuoti literatūra sudaranti 65 darbų nuo sausio 2019 iki spalio 2021 metų šiai specifinei tematikai. Šiame darbe autoriai atrado paradigmos poslinkį, kur tik 7.69% darbų identifikavo savo būdą kaip turinio pagrįstu metodu ir 4.62% kaip bendradarbiavimo filtravimu, grafų pagrįsti darbai buvo klasifikuoti tiek pat 7.69 %. Didžiąją dalį sudarė hibridinių būdu save klasifikuojančių darbų. Šis pokytis parodo, kad grynasis turinio filtravimas palaipsniui buvo papildomas kolaboratyviniais ir grafiniais komponentais, o dominuojančios reprezentacijos priemonės perėjo nuo TF-IDF prie giliojo mokymosi įterpčių (angl. embeddings), pavyzdžiui, Word2Vec, Doc2Vec ir BERT. Kitas svarbūs aspektas galintis prisidėti prie šio baigiamojo darbo yra autorių konstatavimas, kad daugelis sistemų nepateikė tikslinės auditorijos aprašymų – kam tiksliai yra skirtos jų sistemos. Paskutinis ir išsamus tyrimas Pinedo ir kt. (2026) apžvelgiantis literatūra nuo lapkričio 2021 iki gruodžio 2024 patvirtina minėtas tendencijas. Analizuojant 63 darbus autoriai nustatė, kad 79.37 % sistemų naudoja vektorinės erdvės modelio metodus dokumentų reprezentacijai, o įterpčių naudojimas išaugo iki 50.79% visų sistemų. Šiame darbe aiškinama, kad turinio pagrįsti metodai išlieka dominuojantys, dėl šalto-starto problemos. Net 95.23% sistemų remiasi šiais metodais, kaip pagrindiniu šios problemos sprendimo būdu. Naujos publikacijos neturi citavimo istorijos, vartotojų įvertinimų ir dažnai neturi bet kurios kitų vartotojų įsitraukimo informacijos. Tokiame kontekste bendradarbiavimo pagrįstas filtravimas, kuris priklauso nuo tokių sąveikos signalų, sunkiai gali juos rekomenduoti. { Be to, akademiniuose rekomendacijose, vartotojų profiliai paprastai yra arba statiniai (pagrįsti pradiniais temos pasirinkimais), arba netiesiogiai išvesti iš plačių elgesio signalų, pavyzdžiui, paspaudimų elgsena, kurie neatsispindi tikslų pobūdžio. } Pinedo ir kt. (2026) pabrėžia esminį apribojimą, tik 4.76 % sistemų priima laisvos formos tekstinį įvesti, o didžioji dauguma reikalauja struktūrizuotos vartotojo informacijos arba konkretaus straipsnio kaip užklausos taško. 

## **2.4. Didžiųjų kalbos modelių pritaikymas rekomendacinėse sistemose** 

Didžiųjų kalbos modelių (DKM) integracija į rekomendacines sistemas reiškia fundamentalų pokytį nuo tradicinių filtravimo metodų link kontekstą suvokiančių ir semantiškai turtingesniu sprendimų, kur rekomendacija priklauso labiau nuo turinio ir esmės labiau negu istorinių sąveikų arba nuo kitų vartotojų. Tačiau norint giliau suprasti techninį pagrindą, būtina atsižvelgti į transformerių architektūrą(žr. pav.), kuri leidžia šiuos modelius klasifikuoti pagal jų struktūrą į atitinkančią grupę. 

## _2.4.1. Transformerių architektūra_ 

Naudojama transformerių architektūra turi tiesioginę įtaką atliekamai užduočiai rekomendacinėse sistemose. Munson et al. (2025) išskiria tris pagrindines transformerių variacijas. Koduotojo (angl. encoder-only) architektūra naudoja tik kairiąją transformerio dalį, kuri priima 

14 

natūralios kalbos tekstą ir sukuria jo įterptis. Šie modeliai yra pritaikyti kalbos konteksto mokymuisi ir geriausias šios variacijos pavyzdys yra BERT modelis. Dekoderio (angl. decoder-only) architektūra naudoja tik dešiniąją transformerio dalį ir dėl to šie modeliai geba priimti natūralią kalbą ir generuoti statistiškai paremtus tęsinius, todėl jie yra dominuojantys šiuolaikiniuose pokalbių modeliuose, tokiuose kaip GPT modeliai. Koduotojo-dekoderio (angl. encoder-decoder) architektūra priima įvesties seką, ją užkoduoja ir tuomet dekoduoja ir sugeneruoja išvesties seką. Šį struktūra yra ypač naudinga atliekant „tekstas į tekstą“ užduotis, o ryškiausias pavyzdys yra T5 modelis. 

**==> picture [199 x 420] intentionally omitted <==**

## _2.4.2. Didžiųjų kalbos modelių rūšys_ 

Šie architektūriniai skirtumai lemia, kaip modeliai pritaikomi rekomendavimo užduotims. Remiantis Wu et al. (2024) apžvalga, DKM taikymą rekomendacinėse sistemose galima suskirstyti į dvi pagrindines funkcines paradigmas: diskriminatyviuosius (angl. Discriminative LLM arba DLLM4Rec) ir generatyviuosius (angl. Generative LLM arba GLLM4Rec) modelius. (žr.2.2pav) 

15 

**==> picture [395 x 212] intentionally omitted <==**

Diskriminatyvioji paradigmą remiasi koduotojo tipo modeliais, tokiais kaip BERT. Šie modeliai pasižymi stipriomis natūralios kalbos teksto supratimo gebėjimais ir dažniausiai jie naudojami išgauti požymius semantinėms reprezentacijoms (įterptims). Šie modeliai yra papildomai pritaikomi prie specifinės rekomendavimo užduoties naudojant papildoma mokymą arba parametrų derinimą (angl. fine-tuning) arba užklausų derinimą (angl. prompt-tuning). Toks būdas leidžia padidinti rekomendacijų tikslumą ir iš dalies išspręsti naujų elementų šaltojo starto problemą. Dirbtinio intelekto vystymuisi atsirado nauji generatyvieji modeliai, kaip „Claude“, „Gemini“, „Mistral“, „ChatGpt“. Palyginus su diskriminatyviais modeliais šie modeliai yra pranašesni natūralios kalbos generavime. Vietoj to, kad taikyti išmoktas reprezentacijas pritaikyti rekomendacijų sričiai, generatyvinių modelių pagrįsti metodai gali tapti rekomendavimo šaltiniu. Autorių darbe minimi keli būdai kaip tai galima padaryti ir jie paskirstė tai į dvi pagrindines strategijas - reikalaujančias parametrų derinimo (angl. tuning) ir nereikalaujančias parametrų derinimo (angl. non-tuning). Nereikalaujantys derinimo metodai išnaudoja stebėtinus DKM nulinio ar kelių pavyzdžių ( angl. zero/few-shot) generavimo pajėgumus. Tai pasiekiama formuojant specialias instrukcijas (angl. promtping) arba mokantis iš konteksto (angl. in-context learning), kai modeliui pateikiami užduoties pavyzdžiai. Hou ir kt. (2024) įrodė, kad DKM turi daug žadančių „nulinio pavyzdžio“ (angl. zeroshot) arba mokymosi be prieš ankstinių pavyzdžių reitingavimo gebėjimų rekomendacijų užduotims. Susidaro tokia situacija, kur modelis geba įvertinti elemento aktualumą per natūralios kalbos samprotavimus be jokių užduočiai būdingų mokymo duomenų.(Hou ir kt., 2024) He ir kt. (2023) padarė panašų darbą, kur pasireiškė panaši išvada kad DKM modeliai pranokstą patobulintus (angl. fine-tuned) pokalbių rekomendavimo modelius nulinio pavyzdžio aplinkoje. 

Generatyvieji modeliai gali ne tik apdoroti turinį, bet ir veikti kaip visos sistemos valdikliai (agentai), gebantys suprasti vartotojo reikalavimus ir poreiki ar per dialogą, ar prieš iš anksto pateikta 

16 

aprašymą, pagal paieškos sistemos užklausos principus. Tokios sistemos gali papildomai pasitelkti išorinius paieškos ar atminties įrankius, kad pateikti rezultatus. Taip pat derinimo reikalaujantys metodai, tokie kaip instrukcijų derinimas (angl. instruction tuning), leidžia DKM tiksliau atlikti specifines užduotis, kartu išlaikant prisitaikymą prie naujų situacijų. Galiausiai, generatyvieji modeliai atveria kelią didesniems interpretavimo galimybėms, šios sistemos geba generuoti paaiškinimus, kodėl konkretus elementas buvo rekomenduotas. Tai leidžia kurti personalizuotas ir kontekstą suvokiančias sistemas, kurią galima valdyti laisvos formos tekstiniais aprašais. 

Generatyviniai modelių gebėjimai demonstruoja didžiulį potencialą, vien bazinio kalbos modelio integravimas į sistemą dažnai yra nepakankamas sprendžiant sudėtingas, daugiapakopes rekomendavimo užduotis. Siekiant, kad DKM taptų autonomišku ir kryptingu agentu arba visa vertė agentinė sistema reikalingas specialios architektūros pritaikymas. 

## **2.5. Agentiniai rekomendavimo varikliai kaip naujas filtravimo būdas** 

Agentiniai rekomendavimo varikliai gali būti kitas potencialus žingsnis po klasikinių ir giliuojo mokymuisi paremtų sistemų, išplėčiant turinio pagrįstus ir personalizuotus konteksto sąmoningus metodus. Šios sistemos gali ne tik vertinti panašumą tarp elementų, bet ir turi galimybė savarankiškai atrinkti, planuoti, naudoti specialius įrankius bei prisitaikyti prie nuolat kintančių vartotojo tikslų ir poreikio. DKM integracija leidžia pereiti nuo paprasto reitingavimo prie autonominių sistemų, kurios gali „stebėti“ informacijos srautus, formuluoti užklausas ir priimti sprendimus atrankai be nuolatinio žmogaus įsikišimo. Mokslinėje literatūroje, pavyzdžiui, Zhu et al. (2025) suskirstė agentinės rekomendacinės sistemos į keturis funkcinius modulius, tai yra, profiliavimo, atminties, planavimo ir veiksmų. (žr. pav). Kiekvienas komponentas yra atsakingas už savo funkcijas: 

**==> picture [332 x 239] intentionally omitted <==**

17 

1. Profiliavimo modulis (angl. Profile component) yra būtinas siekiant suderinti rekomendacijas su autentiška vartotojo elgsena ir pageidavimais. Šis komponentas susidaro iš kelių kitų elementų, kaip vartotojo savybės, kurios atspindi tiek bendras makro lygmens socialinės tendencijas, tiek mikro atspindantys personalinį skonį. Taip pat rekomenduojamų elementų savybės bei pačio agento vaidmens instrukcijas, kurios apibrėžia specifinę agento užduotį, pavyzdžiui, „veik kaip kelionių patarėjas“) 

2. Atminties modulis (angl. Memory component) DKM kontekste reiškia agento gebėjimą saugoti, atkurti ir naudoti informaciją iš buvusių sąveikų, užduočių ar stebėjimų, siekiant formuoti savo ateities elgseną ir atsakymus. Šioje vietoje gali būti įterptas grįžtamojo ryšio mechanizmas. Atmintis leidžia agentams išlaikyti kontekstą tarp skirtingų sesijų ir nuolat mokytis iš ankstesnių patirčių. Tai transformuoja DKM iš paprastų, pasyvių atsakymų generatorių į adaptyvias, interaktyvias sistemas, gebančias imituoti žmogiškąjį supratimą ir užtikrinti atrinktą ir personalizuotą patirtį. 

3. Planavimo modulis (angl. Planning component) šis komponentas leidžią DKM agentui gavus uždavinį išskaidyti į mažesnius po uždavinius, lengvesniam veiksmų sekos supratimui suskaidant tai į logišką procesą. Šis išskaidymas padeda agentui nustatyti ir pasitelkti tinkamiausius įrankius bei dinamiškai koreguoti savo strategijas remiantis tarpiniais rezultatais, kol pasiekiamas galutinis tikslas. Šis mechanizmas leidžia agentui įgyti didesnę autonomiją ir tikslumą imituojant žmogiškus problemų sprendimo procesus. 

4. Veiksmų modulis (angl. Action component) tai konkrečios užduotys ar operacijos, kurias atlieka agentas. Šie veiksmai yra atliekami remiantis gauta įvestimi ir instrukcijomis. Veiksmai gali apimti teksto generavimą, atsakymų paiešką, informacijos išgavimą, sprendimų priėmimą ar net išorinių sistemų valdymą naudojant išorinius įrankius, API, MCP arba žinių bazes.  Veiksmų modulis yra kritiškai svarbus, nes jis įgalina agentą peržengti pasyvaus kalbos supratimo ribas ir aktvyviai įsitraukti į sprendimų priėmimą bei užduočių vykdymą dinaminėje aplinkoje, pavyzdžiui, gavęs užduoti sukurti kelionės planą, agentas gali savarankiškai filtruoti resursus ir tiesiogiai iškviesti kitų sistemų priėjimo tašką per API arba MCP, nereikalaudama žmogaus įsikišimo. 

Šių modulinių komponentų sąveika gali padėti sukurti filtravimo sistemą, kuri galėtu palaikyti vartotojo domėjimąsi kryptimi bunant „ahead of the curve“ – kas reiškia siekti naujausias tendencijas dirbtinio intelekto srityje. 

Empiriniai rezultatai rodo, kad kelių tokių DKM agentų bendradarbiavimas gali pasiekti arba viršyti žmogaus lygio filtravimo kokybę. Joos ir al. (2025) parodė kad keli DKM agentai su konsensuso balsavimu, gali pasiekti daugiau nei 98% prisiminimo (angl. recall) metrikos filtruojant 

18 

mokslinius straipsnius sisteminėms apžvalgoms, priartėdami prie žmogiško našumo lygio arba jį net viršydami. Šie rezultatai rodo, kad agentinės sistemos gali atlikti kokybiška mokslinių darbų atrinkimu nepraleidžiant svarbių publikacijų ir net gali priartėti prie ekspertų darbo efektyvimo, kas šio darbo atveju tokia sistema gali veikti puikiai kaip geras atrankos įrankis vartotojo domėjimosi sričiai. Filtravimo požiūrių agentiniai varikliai išplečia tradicinę, reaktyvią „užklausa-atsakymas“ seka į potencialiai autonomiškai veikiančią sistemą. Vietoje to, kad vartotojas kasdien formuluotų naujas užklausas, agentai gali nuolat stebėti skirtingus šaltinius, kaip šio darbo kontekste arXiv, periodiškai traukti naujausius dokumentus, atlikti semantinę atranką ir pateikti tik tikslą atitinkančius rezultatus. Tokios sistemos ypač aktualios dinamiškuose duomenyse, kur kasdien atsiranda vis naujesniu darbų ir dažniausiai nėra šie darbai retkarčiais yra pastebėti, kol nepraeis pakankamai laiko. Papildomai kur informacijos kiekis auga greičiau nei naudotojas spėja pakeisti savo srities atradimo strategijas. Šiame kontekste agentiniai rekomendavimo varikliai gali būti vertinami kaip naujas filtravimo būdas, jungiantis vektorinės paieškos, DKM semantinio supratimo ir autonominio planavimo privalumus. 

## **2.6. Panašus sprendimai** 

## _2.6.1. Klasikinės ir turiniu grįstos filtravimo sistemos_ 

Analizuojant ankstyvuosius turinio grįstus filtravimo sprendimus, pamatiniu atskaitos tašku laikoma „ArXiv Sanity Preserver“ GitHub - Karpathy/Arxiv-Sanity-Preserver: Web Interface for Browsing, Search and Filtering Recent Arxiv Submissions · GitHub (2017). Šios platformos duomenų apdorojimas rėmėsi klasikiniai mašininio mokymosi algoritmais. Tekstinių dokumentų atvaizdavimui vektorinėje erdvėje naudotas retųjų vekorių TF-IDF reprezentacijos, o binarinei klasifikacijai ir reitingavimui atraminių vektorių mašinos (angl. Support Vector Machines, SVM). Ši architektūra užtikrino efektyvų panašių straipsnių klasterizavimą remiantis leksinių požymių sutapimais, bet pagrindinis trūkumas buvo gilaus semantinio supratimo stoka. Šis įrankis veikė, kaip greitas paieškos variklis pagal panašių darbų pavyzdžius. 

Viena iš pažangiausių ir atitinkančių naujos kartos mokslinių straipsnių stebėjimo įrankių yra „Scholar Inbox“ platforma. Remiantis kūrėjų publikaciją Flicke et al. (2025) šiai platformai Tai kol kas atviros prieigos sistema, realizuojanti personalizuotą, turinio pagrįsta filtravimą. Skirtingai nei socialinių tinklų sprendimai, kur dažniausiai naudojami bendradarbiavimo mechanizmai, ši sistema eliminuoja socialinio šališkumo problemą, autoriai paminėjo šia problemą kaip „Matthew“ efektas, kur populiarus darbai tampa labiau matomi, o mažiau pastebėti, taip ir lieka nepastebėti dėl vartotojų elgsenos. Svarbiausia šios sistemos funkcija yra pavadinta, kaip angl. „Daily Digest“ t.y. kasdienis susisteminimas arba naujausių einančios dienos publikacijų atrinkimas ir pateikimas vartotojui naudojant el. paštą. Techniškai tai yra periodinis informacijos išgavimo ir reitingavimo modulis. Serverinėje dalyje (angl. Backend) veikia „Celery“ įrankis, leidžiantis valdyti asinchronines 

19 

užduotys, kurios surenka metaduomenis ir straipsnių tekstus iš „arXiv“, „bioRxiv“, „chemRxiv“ ir „medRxiv“, taip remkamos publikacijos iš viešų konferencijų. Atlikus pradinį filtravimą, straipsniai yra surikiuojami naudojant vartotojo priskirta specifinis logistinės  regresijos modelis, kurio išvestis tiesiškai transformuojama į aktualumo skalę nuo -100 iki 100. Sąsajoje integruotas tiesioginis grįžtamojo ryšio mechanizmas, kur vartotojo teigiami ir neigiami įvertinimai (angl. thumbs up/down) veikia kaip anotuoti duomenys. Tokių būdų realizuojamas aktyvusis sistemos mokymasis (angl. active learning), kur po kiekvienos sąveikos klasifikatorius yra derinamas naudojant išreikšta (angl. explicit) elgsena. Klasifikatorius apmokomas arba derinamas naudojant pasvertąją binarinę kryžmininės entropijos (angl. weighted binary cross-entropy) nuostolių funkciją, kuri sprendžia klasių disbalanso problemą tarp mažo teigiamų įvertinimų kiekio ir didelio atsitiktinai parinktų neigiamų pavyzdžių skaičiaus. Autoriai pabrėžia, kad modelio derinimui jie atsitiktinai atrenka 5000 straipsnių, su kuriais vartotojas dar neturėjo sąveikos ir traktuoja juos kaip neigiamus. Tuo tarpų vidutiniškai vartotojai įvertina tik tai apie 78 pavyzdžius, kas dėl veikimo logikos ir sukelia tokį disbalansą. Kitas svarbus aspektas, tai kad „Scholar Inbox“ autorių duomenimis tik 35% visų vartotojų yra aktyvus ir naudoja svetainė. Šis 30 dienų išlaikymo rodiklis (angl. retention rate) autorių žodžiais yra didelis cit. „Šis aukštas vartotojų išlaikymo lygis patvirtina tiek rekomendacijų sistemos veiksmingumą, tiek praktikinę platformos teikiamą naudą“(Flicke et al., 2025), šiame darbe tai neprieštaraujama ir daroma akcentą, kad šis skaičius gali būti pagerintas. Galima padaryti keletas skirtingų prielaidų pirma kiti naudotojai mažiau naudojasi el. paštų, todėl nesugrįžta, antra prielaida, kad šalto starto problema, bei logistinės regresijos kalibravimas atmeta tam tikrą žmonių kiekį, dėl ilgo pildymo. Grįžtant prie šalto starto problematikos, testavimo metų po pirminio atrinkimo prireikė dar papildomai vertinti pirmus 4 rekomenduojamas grupės, kas užtruko 4 dienas, tam kad pasiekti minimaliai patenkinanti rezultatą. 

Šios platformos kūrėjai atliko išsamią dokumentų įterpčių analizę, lygindami tradicinius retuosius (angl. sparse) modelius su giliojo mokymosi tankiaisiomis (angl. dense) reprezentacijomis. Autorių tyrimas parodė, kad klasikinė 10 000 dimensijų TF-IDF reprezentacija pasiekia itin aukštus rezultatus rekomendacinių sistemų nDCG metrikoje (88.67), kas atspindi aukštą aktualiausių straipsnių rikiavimo kokybę. (žr. pav.) 

**==> picture [283 x 86] intentionally omitted <==**

20 

Vis dėlto, produkcinėje aplinkoje buvo išrinktas tankusis „GTE-Large“ transformerio modelis. Rezultatų lentelės duomenys(žr. pav) demonstruoja šio modelio pranašumą sprendžiant binarinės klasifikacijo užduotis, pasiekiant geriausius rezultatus pagal F1 (84,51), kuris reiškia kad modelis optimaliausiai išlaiko balansą tarp tikslumo (angl. precision – išties gerų pasiūlytų straipsnių dalis) ir atgaunamumo (angl. recall – iš visų išties gerų pasiūlytų straipsnių dalis). Taip pat, modelis išsiskiria aukščiausiu subalansuotu tikslumu (78,31). Ši metrika yra kritinė, nes klasikinis tikslumas (angl. accuracy) tokioje sistemoje būtų klaidinantis, dėl klasių disbalanso, kur egizstuoja tūkstančiai neigiamų pavyzdžių ir tik maža dalis įvertinta teigiamai. Subalansuotas tikslumas įrodo, kad sistema efektyviai reaguoja į tiesioginį neigiamą vartotojų grįžtamąjį ryšį. „GTE-L“ modelio stabilumą papildomai patvirtina AUC (86,75), indikuojanti didelę tikimybę, kad aktualus straipsnis gaus aukštesnį įvertinimą nei atsitiktinai parinktas neaktualus. Tyrimo duomenimis GTE architektūra geriau klasifikuoja „sunkiai neigiamus“ (angl. hard negatives) pavyzdžius, tai yra, straipsnius kurie leksiškai yra panašūs į vartotojo anksčiau teigiamai įvertintus darbus, tačiau semantiškai neatitinkančius vartotojo tyrimo specifikai ar domėjimosi specifine sritimi. Paieškos operacijų ir atminties sąnaudų optimizavimui, „GTE-L“ dimensijos buvo sumažintos nuo 1024 iki 256 naudojant PCA metodą, o vektoriai indeksuojami NGT (angl. Neighborhood Graph and Tree) struktūroje, kuri leidžia greitą artimiausio kaimyno paiešką. Atlikus šios platformos analizė ir praktinis testavimas patvirtina, kad toks vektorinės erdvės panaudojimas bei matematinių modelių pritaikymas užtikrina aukšta sistemos našumą ir plečiamumą (angl. scalability). Šie architektūriniai sprendimai leidžia sistemai efektyviai veikti didelėje skalėje, apdorojant plataus spektro mokslinės tematikos duomenų srautus. Vis dėlto, nors ši architektūra efektyviai sprendžia informacijos atgavimo problemą didėlę skale, jos rėmimasis išskirtinai tik matematiniais įrankiais apriboja sistemos galimybes giliaus analizuoti teksto aktualumą tam tikram vartotojui ar argumentuoti priimtus rekomendacinius sprendimus. Taip pat, patys autoriai, pabrėžia, kad vartotojai prašo kelių pomėgių arba domėjimosi šakų įterpimo, bet suprantant, kad tam reikalingas kiekvieno atskiro modelio apmokymo, tai sudarys didelį vartotojo išlaikymo problemą, nes kiekvienam pomėgiui vartotojas turės kiekviena kartą vertinti didelį darbų kieki iš naujo. Šie ribotumai pagrindžia poreikį šiame baigiamajame darbe siūlomai hibridinei architektūrai, kurioje efektyvią vektorinę paiešką papildys semantinį samprotavimą ir paaiškinamumą užtikrinantys DKM agentai. 

21 

## **3. Sistemos specifikacija** 

Literatūros apžvalgoje (2 skyrius) buvo identifikuotos trys pagrindinės esamų mokslinių straipsnių filtravimo ir rekomendavimo sistemų spragos: 

1. Absoliuti dauguma sistemų nepriima laisvos formos tekstinės įvesties, tik 4.76% sistemų leidžia vartotojui natūralia kalba aprašyti savo tikslus Pinedo et al. (n.d.). 

2. Esamos sistemos turi ilgą vartotojo įvedimo laiką (angl. on-boarding) arba pradinį kalibravimą, kurio metu vartotojas turi rankiniu būdu vertinti straipsnius, kad sistema išmoktų jo preferencijas. Derinimo patinkančių arba netinkančių straipsnių etapas buvo ištestuotas „Scholar Inbox“ sistemoje. Šis etapas užtruko 23 min įvertinti 40 straipsnių. 

3. Kelių domėjimosi sričių ribotumas, jau aptartame panašiame sprendime, vartotojai apsibrėžia tik vieną interesų profilį ir jį pakeisti sunku, nes „Scholar Inbox“ pavyzdyje reikėtu pridėti dar vieną logistinę regresiją arba apmokyti naujai praeinant derinimo procesą, o DKM agentai turi stipru „zero-shot“ gabumus. 

4. Esamos sistemos veikia kaip klasikinės paieškos varikliai ir nestebi naujausius straipsnius, kur vartotojas turi ateiti su jau suformuotu klausimu ir jeigu jis stebi kažkokią sritį vartotojas turi atsiminti ir turėti įproti tai tikrinti, o šiuo metų yra mažai stebinčių naujų publikacijų sistemų. 

5. Šiuo metų egzistuoja mažai skirtingų darbų eksperimentuojančiu su agentinė paradigma rekomendavimo uždaviniams, tuo labiau mokslinių straipsnių filtravimui ir rekomendavimui. 

6. Paaiškinamumo trūkumas. Dauguma esamų sistemų veikia, kaip „juodoji dėžė“ rodantys tiktai galutinį skaičių, bet negali paaiškinti kodėl šis objektas yra aktualus vartotojui. 

Šiame skyriuje pristatoma agentinė informacinė sistema, suprojektuota šioms spragoms adresuoti. Pirmiausia formuojami funkciniai ir nefunkciniai reikalavimai, tiesiogiai kylantis iš identifikuotų spragų. Toliau aprašoma sistemos architektūra, jungianti informacijos paieškos metodus su DKM agentiniu vertinimu (3.2 poskyris). Galiausiai pagrindžiami technologiniai sprendimai, priimti realizuojant šią architektūrą (3.3 poskyris). 

## **3.1. Reikalavimų specifikacija** 

Šiuo darbo realizacija orientuota į dirbtinio intelekto inžinierius ir tyrinėtojus kaip pirminė tikslinė auditorija. Šis pasirinkimas grindžiamas empiriniais duomenimis iš „Scholar Inbox“ platformos, Flicke ir kt. (2025) nustatė ir nurodė, kad 29% jų vartotojų domisi mašininiu mokymuisi ir dar 29% vartotojų kompiuterine rega(žr. pav). Tai rodo, kad DI sritis sudaro didžiausią mokslinių publikacijų stebėjimo įrankių vartotojų segmentą, bendrai sudarantys 48% visų naudotojų. Šis 

22 

santykis yra išvestas iš 23 tūkstančių naudotojų. Dėl šios priežasties šis darbas apims arXiv kategorijas cs.AI, cs.CL ir cs.LG, tai leidžia sutelkti vertinimo kokybės optimizavimą vienai, aiškiai apibrėžtai sričiai, prieš plečiant sistemą į kitas disciplinas. 

**==> picture [279 x 268] intentionally omitted <==**

Šiame poskyryje pateikiami sistemos funkciniai ir nefunkciniai reikalavimai bei naudojimo atvejų diagramos. Reikalavimai buvo suformuoti pagal 2 skyriuje atlikus literatūros analize, konkrečiai identifikuotomis esamų mokslinių straipsnių rekomendavimo sistemų spragomis ir agentinės rekomendavimo paradigmos dėmesio nesuteikimu ir jų galimybėmis. 

## _3.1.1. Funkciniai reikalavimai_ 

Funkciniai reikalavimai susideda iš kelių dalių vartotojo profilis ir nustatymai, duomenų surinkimas, filtravimo ir vertinimo procesas, srautas ir peržiūros eiga, asmeninės bibliotekos ir žinių valdymas ir pranešimai. Reikalavimai pateikiami 3.1 lentelėje. 

23 

## 3.1 lentelė. 

## **ID VARTOTOJO PROFILIS IR NUSTATYMAI** 

|**FR1**|Sistema turi skirtuką nustatymai.|
|---|---|
|**FR2**|Sistema priima vartotojo konfigūruojamus filtravimo nustatymus. Nustatymai turi<br>įtraukti kategorijas pagal šaltinio taksonomiją, temų pasirinkimą, sekamų autorių<br>ir laisvos formos tekstinį tikslo aprašymą pateikti.|
|**FR3**|Sistema turėtų leisti stebėti papildomą sritį.|
|**FR3**|Sistema leidžia pasirinkti paaiškinimų lygi asmeniniai bibliotekai paaiškinimų<br>lygį. Lygiai susidaro iš tokių pasirinkimų - paaiškinti kaip profesionalui, kaip<br>nesusijusiam žmogui, kaip vaikui.|
|**FR4**|Sistema išsaugo vartotojo profilį tarp sesijų, įskaitant filtravimo nustatymus,<br>pranešimų konfigūraciją, įvertinimą.|
|**FR5**|Vartotojas gali bet kuriuo metu keisti nustatymus. Nauji nustatymai taikomi<br>ateities filtravimams.|
||**DUOMENŲ SURINKIMAS**|
|**FR6**|Sistema automatiškai surenka einamosios dienos publikacijas. Surenkami<br>metaduomenys, unikalus identifikavimo numeris, pavadinimas, santrauka,<br>autoriai, kategorijos, publikavimo data, nuorodos į PDF ir šaltinį.|
|**FR7**|Sistema eliminuoja dublikatus naudodama identifikavimo numerį. Straipsnis<br>nerodomas pakartotinai, nebent publikacija turi atnaujinta versiją|
||**FILTRAVIMO IR VERTINIMO PROCESAS**|
|**FR8**|Sistema turi atlikti trijų etapų filtravimą tokia seka:<br>1. Filtravimas pagal kategorijų ir raktažodžių taisyklės.<br>2. Leksinis filtravimas naudojant BM25 ir semantinis panašumas naudojant<br>SPECTER2.<br>3. DKM agentinis atrinkimas ir vertinimas su struktūriniais paaiškinimais.|
|**FR9**<br>Sistema sukuria struktūrinę vertinimo išvestį kiekvienam kandidatiniam<br>straipsniui. Sprendimą (priimti, atmesti), skaitinį balą, vertinimo priežastis ir<br>vartotojui skirtą paaiškinimą natūralia kalba.||



24 

|**FR10**|Sistema generuoja geriausių pasirinkimų sąrašą pranešimams pagal vertinimo<br>rezultatus.|
|---|---|
||**SRAUTAS IR PERŽIŪROS DARBO EIGA**|
|**FR11**|Sistema turi skirtuką srautas (angl. „feed“).|
|**FR12**|Sistema sukuria srautą susidedanti iš išfiltruotų straipsnių, kur atvaizduojamas<br>pavadinimas, autoriai, santraukos peržiūra, vertinimo balas, agento paaiškinimas,<br>nuoroda į šaltinį ir į PDF.|
|**FR13**|Sistema suteikia vertinimo galimybę vartotojui veiksmo pavidalu priimti arba<br>atmesti straipsnį.<br> Veiksmas „atmesti“ saugomas ir naudojamas tolesniame filtravime kaip<br>grįžtamasis ryšys vertintojo agentui.<br> Veiksmas „priimti“ prideda straipsnį į asmeninę biblioteką.|
|**FR14**|Sistemą gali priimti trumpa tekstinį komentarą atmetant straipsnį. Komentaras<br>saugomas kaip struktūrinis grįžtamasis ryšys ir pateikiamas vertinimo agentui<br>būsimuose filtravimo cikluose.|
||**ASMENINĖ BIBLIOTEKA IR ŽINIŲ VALDYMAS**|
|**FR15**|Sistema turi skirtuką asmeninė biblioteka. Joje pateikiami „priimti“ straipsniai.|
|**FR16**|Sistema turėtų sugeneruoti paaiškinimą pagal nustatymuose pasirinktą lygį.|
||**PRANEŠIMAI**|
|**FR17**|Sistema turi  išsiųsti naudotojui pranešimą į el. paštą sudarant TOP5 straipsnius<br>pagal naudotojo domėjimosi sritį. el. paštu arba į slack.|
|**FR18**<br>Vartotojas konfigūruoja pranešimų nustatymus – kanalą ir siuntimo laiką ir kurią<br>sritį stebėti.||



Vėliau kai realizacija eina funkcionalumas. 

Iš pateiktų reikalavimų svarbu išskirti keletas. Svarbiausia funkcinių reikalavimų dalis yra pranešimu grupė. Reikalavimas FR17 tiesiogiai padeda vartotojui stebėti jo tematikos plėtrą, be papildomo įsitraukimo apdorojant didėli straipsnių kiekį. Kitas svarbūs funkcionalumas yra asmeninė biblioteka leidžianti greitai suprasti apie ką kalbama tam tikrame straipsnyje pagal nustatymuose pasirinktus lygius asmeninėje bibliotekoje. Išskiriantis punktas yra paaiškinimas paskutinės 

25 

filtravimo fazės sąrašas, kuriame yra apibrėžta kodėl straipsnis buvo rekomenduotas. Taip pat verta paminėti kad sistema priima laisvos formos tekstą apibrėžianti vartotojo poreikį. 

## _3.1.2. Nefunkciniai reikalavimai_ 

Nefunkciniai reikalavimai apibrėžia sistemos kokybės atributus, kaip atsekamumas, plečiamumas, saugumas. Jie buvo suformuoti atsižvelgiant į pirminės versijos prototipo lygmens poreikį, t.y. vienas vartotojas, ribotos kategorijų rinkinys, ~500-1000 straipsnių per dieną ir agentinės sistemos specifiką, kur API kaštai yra pagrindinis apribojimas. Reikalavimai pateikiami 3.2 lentelėje. 

**==> picture [450 x 485] intentionally omitted <==**

**----- Start of picture text -----**<br>
ID  Kategorija  Nefunkciniai reikalavimai  Metrika ir tikslas<br>NFR1  Veiksmingumas Filtravimo ciklas apdoroja iki 500  Iki 10 min ~ 100-200<br>publikacijų  publikacijoms<br>NFR2  Mastelio  Sistema išlieka veiksminga ir esant  Iki 1000 straipsnių.<br>valdymas  padidėjusiam publikacijų srautui<br>NFR3  Atsekamumas  Kiekvieno  vykdymo  tarpiniai  ir  Pilna  vykdymo<br>galutiniai rezultatai saugomi  reprodukcija  derinimo<br>tiskalams<br>NFR4  Autentifikacija  Prieigos  kontrolė  prie  sistemos  Bazinė autentifikacija<br>sąsajos.<br>NFR5  Plečiamumas  Aiškus API kontraktai tarp posistemių Modulinė architektūra su<br>dokumentuotomis<br>sąsajomis<br>NFR6  Saugumas  Pranešimų kanalas turi būti saugiai  Kanalo  reikšmės<br>išsaugotas  šifravimas,  iššifravimas<br>siuntimo metų.<br>**----- End of picture text -----**<br>


26 

## _3.1.3. Use-case diagramos_ 

Šiame poskyryje pateikiamos sistemos naudojimo atvejų (angl. use case) diagramą, apibendrinančią kokias galimybes pasiekiamos naudotojui.  Identifikuoti 5 pagrindiniai atvejai kurie 

atspindės sistemos gebėjimus. UML naudojimo atvejų diagrama pateikiam 3.X paveiksle. 

**==> picture [454 x 310] intentionally omitted <==**

Naudojimo atvejai : 

- UC1. Konfigūruoti filtravimo tikslus – vartotojas apibrėžia arXiv kategorijas, raktažodžius, sekamus autorius (pasirinktinai) ir aprašo laisvos formos tikslą natūralia kalba. Prieš-sąlygos: vartotojas turi jau autentifikuotis sistemoje. Pagrindinis scenarijus: 

   1. Vartotojas atidaro nustatymų puslapį. 

   2. Sistemoje atsidaro prietaisų skydelis su nustatymais. 

   3. Pasirenka arXiv kategorijas iš pateikto sąrašo (pvz., cs.AI, cs.CL, cs.LG). 

   4. Įveda raktažodžius ir temas, kurios domina vartotoją. 

   5. Pasirinktinai nurodo sekamus autorius. 

   6. Laisvos formos tekto lauke natūralia kalba aprašo savo tikslą arba tiksliai kas jam yra įdomų į kurias dalis reikėtu atsižvelgti filtravimo metų. 

   7. Pasirinktinai gali pasirenka asmens bibliotekos paaiškinimo lygį. 

27 

   8. Patvirtina nustatymus. 

- UC2. Peržiūrėti srautą – vartotojas turi galimybę naršyti išfiltruotų publikacijų rezultatus prietaisų skydelyje su vertinimo paaiškinimais, kurie pateikti pagal anksčiau nustatytus kriterijus. Prieš-sąlygos: nustatyti filtravimo parametrai, įvykdytas filtravimo ciklas. Scenarijus: 

   1. Vartotojas atidaro srauto puslapį. 

   2. Atsidaro prietaisų skydelis su išfiltruotomis publikacijomis. 

   3. Vartotojas peržiūri esamus straipsnius. 

   4. Vartotojas peržiūri kriterijus kodėl straipsnis buvo rekomenduotas. 

   5. Vartotojas gali įvertinti straipsnį (UC3). 

   6. Patinkančius straipsnius iš santraukos, naudotojas gali skaityti paspaudus nuoroda į šaltinį. 

- UC3. Įvertinti (priimti/atmesti) – naudotojas turi galimybė priimti publikaciją į savo asmeninę biblioteką arba ją atmesti grįžtamajam atsakui. Prieš-sąlygos: pabaigtas filtravimo ciklas, vartotojas turi peržiūrėti srautą. Scanarijus: 

   1. Naudotojas peržiūrėjęs publikaciją gali priimti ją arba atmesti. 

   2. Jeigu vartotojas priima publikaciją, jį automatiškai atsiranda asmeninėje bibliotekoje. 

   3. Jeigu vartotojas atmeta publikacija, sistema paprašo trumpą komentarą kodėl jį buvo atmestą ir ši informacija keliauja tiesiai vertinimo agentui, kaip grįžtamasis atsakas ateinantiems filtravimams. 

- UC4. Gauti pranešimus – vartotojas gauna pranešimus į savo nustatytą kanalą. Priešsąlygos: vartotojas nustatė pranešimų kanalą, vartotojas nustatė pranešimų laiką. Scenarijus: 

   1. Sistema pagal nustatyta laiką, atlieka filtravimo ciklą ir išsiunčia pranešimą su TOP5 rekomendavimo sąrašų. 

   2. Vartotojas peržiūri atsiųstą sąrašą. 

   3. Vartotojas paspaudžia patikusią publikaciją 

   4. Vartotojas perkeliamas į prietaisų skydelį su atidaryta šio straipsnio santrauka. 

   5. Vartotojas gali daryti viską kas aprėpia kitus atvejus. 

- UC5. Peržiūrėti biblioteka – vartotojas gali grįžti prie jau seniau priimtas publikacijas ir gali greitai atnaujinti žinias pasinaudodamas sistemos paaiškinimu. Prieš-sąlygos: buvo atliktas filtravimas, vartotojas buvo paspaudęs priimti bent vienam straipsniui. Scenarijus: 

28 

1. Naudotojas atidarė puslapį su asmenine biblioteka. 

2. Naudotojas paspaudžia perkeltą publikaciją. 

3. Naudotojas gali paspausti mygtuką „paaiškinti“ 

4. Sistema generuoja paaiškinimą pagal anksčiau nustatytą lygį. 

Pateikti naudojimo atvejai atspindi sąveiką su sistema. 

## **3.2. Architektūrinis projektavimas** 

Supratus kokias funkcinius ir nefunkcinius reikalavimus, galima pradėti architektūros apžvalga. 

## _3.2.1. Dokumentų nuskaitymas_ 

## _3.2.2. Žemo lygio architektūra_ 

## **3.3. Technologijų parinkimas** 

_Refleksija kurias technologijas parinkti. Didžiausia refleksija (Langgraph, CrewAi,autogen) 3.3.1. Dokumentų nuskaitymas_ 

Sukurti tokia sistema reikalinga efektyvi PDF parsinimo logiką arba net visas procesas, kadangi PDF failai yra sunkiausi ištraukimo atžvilgiu, mokslinė specifika - dažnai naudojamas dviejų stulpelių formatas, bei formulės ir grafikai padaro šį uždavinį dar sunkesniu.(Adhikari & Agarwal, 2025) Todėl reikalingas preliminarus technologinis atrinkimas, bei šios dalies architektūros sugalvojimas. Adhikari & Agarwal (2025) padarytas tyrimas parodo, kad moksliniams dokumentams geriausius išgavimo rezultatus parodo – Pypdifum, parodžius geriausius rezultatus metrikuose (F1, Tikslumas,BLUE)(žr.pav). 

**==> picture [455 x 90] intentionally omitted <==**

Galima pamatyti kad F1 yra 0.85, Tikslumas 0.90 ir BLUE 0.70. Taip pat  svarbu paminėti, kad Atgaunamus yra arti geriausio rodant 0.8063, kaip geriausias 0.8137, o tai sudaro tik 0.0074 skirtumo. Tai preliminarus pasirinkimas yra pypdfium. Kitos technologijos kurios galėtu atlikti šį darbą gerai 

29 

galėtų būti MinerU arba Marker. Šie įrankiai yra jau didėli sprendimai, kurie raikalaus architektūrinių sprendimu, kaip pasinaudojimas debesijos kompiuterija. 

30 

## **Sistemos tinkamumo įvertinimas / Tyrimo rezultatai** 

## **3.4. Antro lygio skyriai** 

Pagrindinis tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas 

tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas. 

## **3.5. Antro lygio skyriai** 

## _3.5.1. Trečio lygio skyriai_ 

Pagrindinis tekstas tekstas tekstas tekstas. 

## _3.5.2. Trečio lygio skyriai_ 

Pagrindinis tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas 

tekstas tekstas tekstas tekstas tekstas tekstas tekstas tekstas. 

31 

