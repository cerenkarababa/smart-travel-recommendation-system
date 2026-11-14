
document.addEventListener("DOMContentLoaded", () => {
    const background = document.querySelector(".background-image");

    if (!background) {
        console.error("Background element was not found.");
        return;
    }

    const images = [
        // Tropical paradise
        "https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=2400&q=90",

        // Northern lights - Iceland
        "https://images.unsplash.com/photo-1531366936337-7c912a4589a7?auto=format&fit=crop&w=2400&q=90",

        // Japan - cherry blossoms
        "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=2400&q=90",

       // Istanbul - Galata Tower and Golden Horn Bridge
"https://images.unsplash.com/photo-1781628449518-2c7f3b14d40d?auto=format&fit=crop&w=2400&q=90",

        // Switzerland - Alps
        "https://images.unsplash.com/photo-1531366936337-7c912a4589a7?auto=format&fit=crop&w=2400&q=90",

        // Santorini - Greece
        "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=2400&q=90",

        // Desert landscape
        "https://images.unsplash.com/photo-1509316785289-025f5b846b35?auto=format&fit=crop&w=2400&q=90",

        // Venice - Italy
        "https://images.unsplash.com/photo-1514890547357-a9ee288728e0?auto=format&fit=crop&w=2400&q=90",

        // Iceland - dramatic landscape
        "https://images.unsplash.com/photo-1476610182048-b716b8518aae?auto=format&fit=crop&w=2400&q=90",

        // Ocean escape
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=2400&q=90"
    ];

    let currentIndex = 0;

    function changeBackground() {
        const nextIndex = (currentIndex + 1) % images.length;
        const nextImage = new Image();

        nextImage.onload = () => {
            background.style.backgroundImage =
                `url("${images[nextIndex]}")`;

            currentIndex = nextIndex;

            console.log("Background changed:", nextIndex + 1);
        };

        nextImage.onerror = () => {
            console.error("Image could not be loaded:", images[nextIndex]);
            currentIndex = nextIndex;
        };

        nextImage.src = images[nextIndex];
    }

    // Preload all images
    images.forEach((url) => {
        const image = new Image();
        image.src = url;
    });

    // Change background every 7 seconds
    setInterval(changeBackground, 7000);
});
