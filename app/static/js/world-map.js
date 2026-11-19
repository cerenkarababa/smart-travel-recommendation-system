
(() => {

    const regionNames = {
        e: { en: "Europe", tr: "Avrupa" },
        n: { en: "North America", tr: "Kuzey Amerika" },
        c: { en: "Caribbean", tr: "Karayipler" },
        a: { en: "Asia", tr: "Asya" },
        s: { en: "South America", tr: "Güney Amerika" },
        m: { en: "Middle East", tr: "Orta Doğu" },
        f: { en: "Africa", tr: "Afrika" },
        o: { en: "Oceania", tr: "Okyanusya" }
    };

    const mapTranslations = {
        en: {
            eyebrow: "EXPLORE THE WORLD",
            title: "Discover destinations.",
            description: "Explore destinations around the world and find your next adventure.",
            search: "Search a destination or country...",
            all: "All regions",
            loading: "Loading destinations...",
            loaded: "destinations are waiting to be explored.",
            error: "Destinations could not be loaded.",
            noResults: "No matching destinations found.",
            country: "Country",
            region: "Region",
            climate: "Climate",
            budget: "Budget",
            season: "Best season",
            descriptionLabel: "About this destination",
            noImage: "Image unavailable",
            photographer: "Photo by",
            license: "License",
            viewSource: "View original photo"
        },
        tr: {
            eyebrow: "DÜNYAYI KEŞFET",
            title: "Destinasyonları keşfet.",
            description: "Dünyanın dört bir yanındaki destinasyonları keşfet ve bir sonraki maceranı bul.",
            search: "Destinasyon veya ülke ara...",
            all: "Tüm bölgeler",
            loading: "Destinasyonlar yükleniyor...",
            loaded: "destinasyon keşfedilmeyi bekliyor.",
            error: "Destinasyonlar yüklenemedi.",
            noResults: "Aramana uygun destinasyon bulunamadı.",
            country: "Ülke",
            region: "Bölge",
            climate: "İklim",
            budget: "Bütçe",
            season: "En iyi sezon",
            descriptionLabel: "Destinasyon hakkında",
            noImage: "Fotoğraf bulunamadı",
            photographer: "Fotoğrafçı",
            license: "Lisans",
            viewSource: "Orijinal fotoğrafı görüntüle"
        }
    };

    const mapElement = document.getElementById("worldMap");

    if (mapElement && window.L) {

        const worldMap = L.map("worldMap", {
            scrollWheelZoom: false
        }).setView([25, 10], 2);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 18
        }).addTo(worldMap);

        const markerGroup = L.markerClusterGroup({
            showCoverageOnHover: false,
            spiderfyOnMaxZoom: true,
            maxClusterRadius: 45
        });

        worldMap.addLayer(markerGroup);

        let allDestinations = [];

        const searchInput = document.getElementById("mapSearch");
        const regionFilter = document.getElementById("mapRegionFilter");
        const mapStatus = document.getElementById("mapStatus");
        const languageSwitcher = document.getElementById("languageSwitcher");

        function getLanguage() {
            return languageSwitcher && languageSwitcher.value === "tr"
                ? "tr"
                : "en";
        }

        function addDetailRow(container, label, value) {
            if (!value) return;

            const row = document.createElement("div");
            row.style.marginTop = "7px";
            row.style.fontSize = "13px";

            const strong = document.createElement("strong");
            strong.textContent = label + ": ";

            const span = document.createElement("span");
            span.textContent = value;

            row.append(strong, span);
            container.appendChild(row);
        }

        function createPopup(destination) {

            const language = getLanguage();
            const t = mapTranslations[language];

            const content = document.createElement("div");
            content.style.width = "260px";
            content.style.maxWidth = "100%";
            content.style.fontFamily = "Arial, sans-serif";

            if (destination.image_url) {

                const image = document.createElement("img");
                image.src = destination.image_url;
                image.alt = destination.destination_name || "";
                image.loading = "lazy";
                image.style.width = "100%";
                image.style.height = "155px";
                image.style.objectFit = "cover";
                image.style.borderRadius = "9px";
                image.style.display = "block";

                image.onerror = () => {
                    image.style.display = "none";
                };

                content.appendChild(image);

            } else {

                const noImage = document.createElement("div");
                noImage.textContent = t.noImage;
                noImage.style.padding = "25px";
                noImage.style.background = "#eee9df";
                noImage.style.textAlign = "center";
                noImage.style.borderRadius = "9px";

                content.appendChild(noImage);
            }

            const title = document.createElement("h3");
            title.textContent = destination.destination_name || "";
            title.style.margin = "12px 0 5px";
            title.style.fontSize = "18px";
            title.style.color = "#17283f";

            content.appendChild(title);

            const country = document.createElement("div");
            country.textContent = `${t.country}: ${destination.country || "-"}`;
            country.style.fontSize = "13px";

            content.appendChild(country);

            addDetailRow(
                content,
                t.region,
                regionNames[destination.region]?.[language] || null
            );

            addDetailRow(content, t.climate, destination.climate);
            addDetailRow(content, t.budget, destination.budget_level);
            addDetailRow(content, t.season, destination.best_season);

            if (destination.description) {

                const descriptionTitle = document.createElement("div");
                descriptionTitle.textContent = t.descriptionLabel;
                descriptionTitle.style.fontWeight = "bold";
                descriptionTitle.style.marginTop = "12px";
                descriptionTitle.style.fontSize = "13px";

                const description = document.createElement("p");
                description.textContent = destination.description;
                description.style.fontSize = "13px";
                description.style.lineHeight = "1.5";
                description.style.margin = "5px 0";

                content.append(descriptionTitle, description);
            }

            if (destination.source_page) {

                const source = document.createElement("a");
                source.href = destination.source_page;
                source.target = "_blank";
                source.rel = "noopener noreferrer";
                source.textContent = t.viewSource;
                source.style.display = "block";
                source.style.marginTop = "12px";
                source.style.fontSize = "12px";

                content.appendChild(source);
            }

            if (destination.image_author || destination.image_license) {

                const attribution = document.createElement("div");
                attribution.style.fontSize = "11px";
                attribution.style.color = "#777";
                attribution.style.marginTop = "8px";

                if (destination.image_author) {
                    attribution.textContent =
                        `${t.photographer}: ${destination.image_author}`;
                }

                if (destination.image_license) {
                    const license = document.createElement("div");
                    license.textContent =
                        `${t.license}: ${destination.image_license}`;
                    attribution.appendChild(license);
                }

                content.appendChild(attribution);
            }

            return content;
        }

        function filterDestinations() {

            const language = getLanguage();
            const t = mapTranslations[language];

            const searchTerm = searchInput.value.trim().toLocaleLowerCase();
            const selectedRegion = regionFilter.value;

            markerGroup.clearLayers();

            const filtered = allDestinations.filter(destination => {

                const name = (destination.destination_name || "").toLocaleLowerCase();
                const country = (destination.country || "").toLocaleLowerCase();

                const matchesSearch =
                    name.includes(searchTerm) ||
                    country.includes(searchTerm);

                const matchesRegion =
                    selectedRegion === "all" ||
                    destination.region === selectedRegion;

                return matchesSearch && matchesRegion;
            });

            filtered.forEach(destination => {

                const marker = L.circleMarker(
                    [destination.latitude, destination.longitude],
                    {
                        radius: 6,
                        color: "#fffdf8",
                        weight: 1.5,
                        fillColor: "#b99a69",
                        fillOpacity: 0.95
                    }
                );

                marker.bindPopup(createPopup(destination), {
                    maxWidth: 300
                });

                markerGroup.addLayer(marker);
            });

            mapStatus.textContent = filtered.length === 0
                ? t.noResults
                : `${filtered.length.toLocaleString()} ${t.loaded}`;
        }

        function updateMapLanguage() {

            const language = getLanguage();
            const t = mapTranslations[language];

            document.getElementById("mapEyebrow").textContent = t.eyebrow;
            document.getElementById("mapTitle").textContent = t.title;
            document.getElementById("mapDescription").textContent = t.description;

            searchInput.placeholder = t.search;
            regionFilter.options[0].textContent = t.all;

            Object.entries(regionNames).forEach(([code, names], index) => {
                regionFilter.options[index + 1].textContent = names[language];
            });

            filterDestinations();
        }

        async function loadDestinations() {

            mapStatus.textContent = mapTranslations[getLanguage()].loading;

            try {

                const response = await fetch("/api/destinations/map");
                const data = await response.json();

                if (!response.ok || !data.success) {
                    throw new Error(data.message || "Map request failed.");
                }

                allDestinations = Array.isArray(data.destinations)
                    ? data.destinations
                    : [];

                filterDestinations();

            } catch (error) {

                console.error("World map error:", error);
                mapStatus.textContent = mapTranslations[getLanguage()].error;
            }
        }

        searchInput.addEventListener("input", filterDestinations);
        regionFilter.addEventListener("change", filterDestinations);

        if (languageSwitcher) {
            languageSwitcher.addEventListener("change", updateMapLanguage);
        }

        updateMapLanguage();
        loadDestinations();

        setTimeout(() => {
            worldMap.invalidateSize();
        }, 300);
    }

})();
