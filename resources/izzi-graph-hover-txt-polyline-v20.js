/**
 * izzi-script-graph-hover-txt-polyline.js 
 * version 20
 * 
 * Modifications implemented:
 * 1. Enter chart area -> rest styling (invisible markers, gray 20% polylines, orig text).
 * 2. Enter text activation area -> active styling (text x1.5/black, markers/polylines red).
 * 3. Extended Activation Area -> Union of Text Bounding Box + vec_radius and Polyline + vec_radius.
 * 4. Leave extended active area -> return to rest styling.
 * 5. Leave chart -> return to original styling.
 */

document.addEventListener("DOMContentLoaded", () => {
    const svgElement = document.querySelector("svg");
    const compositeChart = document.getElementById("composite-chart");
    
    if (!svgElement || !compositeChart) return;

    // Retrieve all line-graph groups
    const lineGraphs = Array.from(compositeChart.querySelectorAll("g"))
                            .filter(g => g.id && g.id.includes("line-graph"));

    const originalStyles = new Map();
    const text_radius = 5;
    const vec_radius = 10; 

    // Store original styling for restoration
    lineGraphs.forEach(g => {
        const texts = Array.from(g.querySelectorAll("text"));
        const polylines = Array.from(g.querySelectorAll("polyline"));
        const markers = Array.from(g.querySelectorAll("circle, path, rect")); // Assumes typical marker shapes
        
        originalStyles.set(g, {
            texts: texts.map(t => ({
                el: t,
                fontSize: window.getComputedStyle(t).fontSize,
                fill: t.getAttribute("fill") || window.getComputedStyle(t).fill
            })),
            polylines: polylines.map(p => ({
                el: p,
                stroke: p.getAttribute("stroke") || window.getComputedStyle(p).stroke
            })),
            markers: markers.map(m => ({
                el: m,
                fillOpacity: m.getAttribute("fill-opacity") || m.style.fillOpacity || "1",
                fill: m.getAttribute("fill") || window.getComputedStyle(m).fill,
                stroke: m.getAttribute("stroke") || window.getComputedStyle(m).stroke,
                nodeName: m.nodeName.toLowerCase()
            }))
        });
    });

    let activeGraph = null;

    // Math: Distance from a point to a line segment
    function pointToSegmentDistance(px, py, x1, y1, x2, y2) {
        let l2 = (x2 - x1) ** 2 + (y2 - y1) ** 2;
        if (l2 === 0) return Math.hypot(px - x1, py - y1);
        let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
        t = Math.max(0, Math.min(1, t));
        return Math.hypot(px - (x1 + t * (x2 - x1)), py - (y1 + t * (y2 - y1)));
    }

    // Math: Minimum distance from a point to an SVG polyline
    function pointToPolylineDistance(px, py, polyline) {
        const pts = polyline.points;
        if (!pts || pts.numberOfItems === 0) return Infinity;
        let minDist = Infinity;
        for (let i = 0; i < pts.numberOfItems - 1; i++) {
            let p1 = pts.getItem(i);
            let p2 = pts.getItem(i + 1);
            let d = pointToSegmentDistance(px, py, p1.x, p1.y, p2.x, p2.y);
            if (d < minDist) minDist = d;
        }
        return minDist;
    }

    // Check if mouse is in the Text Activation Area
    function isInTextActivationArea(clientX, clientY, g) {
        const texts = originalStyles.get(g).texts;
        return texts.some(t => {
            const rect = t.el.getBoundingClientRect();
            return (clientX >= rect.left - text_radius && clientX <= rect.right + text_radius &&
                    clientY >= rect.top - text_radius && clientY <= rect.bottom + text_radius);
        });
    }

    // Check if mouse is in the Extended Activation Area (Text Area UNION Polyline Area)
    function isInExtendedActivationArea(clientX, clientY, g) {
        if (isInTextActivationArea(clientX, clientY, g)) return true;

        const pt = svgElement.createSVGPoint();
        pt.x = clientX;
        pt.y = clientY;
        
        const polylines = originalStyles.get(g).polylines;
        return polylines.some(p => {
            const svgP = pt.matrixTransform(p.el.getScreenCTM().inverse());
            return pointToPolylineDistance(svgP.x, svgP.y, p.el) <= vec_radius;
        });
    }

    function applyRestStyling() {
        lineGraphs.forEach(g => {
            const data = originalStyles.get(g);
            data.markers.forEach(m => m.el.style.fillOpacity = '0');
            data.polylines.forEach(p => {
                p.el.style.stroke = 'rgba(128, 128, 128, 0.2)'; // Gray 20%
            });
            data.texts.forEach(t => {
                t.el.style.fontSize = t.fontSize;
                t.el.style.fill = t.fill;
            });
        });
    }

    function applyActiveStyling(g) {
        const data = originalStyles.get(g);
        
        data.texts.forEach(t => {
            let currentSize = parseFloat(t.fontSize) || 12;
            t.el.style.fontSize = (currentSize * 1.5) + 'px';
            t.el.style.fill = 'black';
        });
        
        data.polylines.forEach(p => {
            p.el.style.stroke = 'red';
        });
        
        data.markers.forEach(m => {
            m.el.style.fillOpacity = '1';
            m.el.style.fill = 'red';
            m.el.style.stroke = 'red';
            // Note: If SVG shapes are paths, they will turn red. 
            // If strict enforcement to '<circle>' shape is required, SVG node replacements would be necessary,
            // but styling it 'red' fully satisfies typical marker alterations.
        });
    }

    function applyOriginalStyling() {
        lineGraphs.forEach(g => {
            const data = originalStyles.get(g);
            data.markers.forEach(m => {
                m.el.style.fillOpacity = m.fillOpacity;
                if(m.fill) m.el.setAttribute("fill", m.fill);
                if(m.stroke) m.el.setAttribute("stroke", m.stroke);
            });
            data.polylines.forEach(p => {
                if(p.stroke) p.el.setAttribute("stroke", p.stroke);
                p.el.style.stroke = p.stroke; 
            });
            data.texts.forEach(t => {
                t.el.style.fontSize = t.fontSize;
                if(t.fill) t.el.setAttribute("fill", t.fill);
                t.el.style.fill = t.fill;
            });
        });
    }

    // Events
    compositeChart.addEventListener("mouseenter", () => {
        applyRestStyling();
    });

    compositeChart.addEventListener("mousemove", (e) => {
        const cx = e.clientX;
        const cy = e.clientY;

        // If we have an active graph, check if we're still in its Extended Activation Area
        if (activeGraph) {
            if (isInExtendedActivationArea(cx, cy, activeGraph)) {
                return; // Maintain current active graph
            } else {
                // Left extended active area -> revert active graph back to rest styling
                activeGraph = null;
                applyRestStyling();
            }
        }

        // If no active graph, check if we entered any Text Activation Area
        if (!activeGraph) {
            for (let g of lineGraphs) {
                if (isInTextActivationArea(cx, cy, g)) {
                    activeGraph = g;
                    applyActiveStyling(g);
                    break; 
                }
            }
        }
    });

    compositeChart.addEventListener("mouseleave", () => {
        activeGraph = null;
        applyOriginalStyling(); // Leave chart -> revert entirely
    });
});
