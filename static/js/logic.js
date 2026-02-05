import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Global variables for 3D scene
let scene, camera, renderer, controls, mesh;

// --- MAIN FUNCTIONS ---

window.startGeneration = async function() {
    const prompt = document.getElementById('promptInput').value;
    if (!prompt) return alert("Please type something first!");

    // UI Updates
    document.getElementById('inputSection').classList.add('hidden');
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('results').classList.add('hidden');

    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt })
        });

        const data = await response.json();

        if (data.success) {
            showResults(data);
        } else {
            alert("Error: " + data.error);
            resetApp();
        }
    } catch (e) {
        alert("Connection failed: " + e);
        resetApp();
    }
};

window.resetApp = function() {
    document.getElementById('inputSection').classList.remove('hidden');
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('results').classList.add('hidden');
    document.getElementById('promptInput').value = "";
    
    // Clear 3D scene memory
    if (mesh) {
        scene.remove(mesh);
        mesh.geometry.dispose();
        mesh.material.dispose();
        mesh = null;
    }
};

window.sendFeedback = async function(action) {
    try {
        const response = await fetch('/feedback', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: action})
        });
        const data = await response.json();
        alert(data.message);
    } catch (e) {
        alert("Could not send feedback");
    }
};

function showResults(data) {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('results').classList.remove('hidden');
    
    document.getElementById('designTitle').innerText = data.design_title;
    
    // Set download links
    document.getElementById('downloadStl').href = data.stl_url;
    
    const stepBtn = document.getElementById('downloadStep');
    if (data.step_url) {
        stepBtn.href = data.step_url;
        stepBtn.style.display = 'inline-block';
    } else {
        stepBtn.style.display = 'none';
    }
    
    // Load 3D Model
    init3DViewer();
    loadSTL(data.stl_url);
}

// --- 3D VIEWER FUNCTIONS ---

function init3DViewer() {
    const container = document.getElementById('viewer3d');
    
    // If renderer exists, just resize it
    if (renderer) {
        const width = container.clientWidth;
        const height = container.clientHeight;
        renderer.setSize(width, height);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        return;
    }

    // Scene setup
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a); // Match background
    
    // Camera
    camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(100, 100, 100);

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    // Controls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // Lights
    const light1 = new THREE.DirectionalLight(0xffffff, 2);
    light1.position.set(1, 1, 1);
    scene.add(light1);
    
    const light2 = new THREE.DirectionalLight(0xffffff, 1);
    light2.position.set(-1, -1, -0.5);
    scene.add(light2);
    
    const ambient = new THREE.AmbientLight(0x404040);
    scene.add(ambient);

    // Animation Loop
    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();
    
    // Handle resize
    window.addEventListener('resize', () => {
        if (!container) return;
        const width = container.clientWidth;
        const height = container.clientHeight;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
    });
}

function loadSTL(url) {
    const loader = new STLLoader();
    loader.load(url, function (geometry) {
        // Red Color Material
        const material = new THREE.MeshPhongMaterial({ 
            color: 0xdc2626, // Red
            specular: 0x111111, 
            shininess: 100 
        });
        
        if (mesh) scene.remove(mesh);
        
        mesh = new THREE.Mesh(geometry, material);
        
        // Center the geometry
        geometry.computeBoundingBox();
        const center = geometry.boundingBox.getCenter(new THREE.Vector3());
        mesh.position.sub(center); 
        
        // Rotate to upright
        mesh.rotation.x = -Math.PI / 2;
        
        scene.add(mesh);
        
        // Auto-zoom
        fitCameraToSelection(camera, controls, [mesh]);
    });
}

function fitCameraToSelection(camera, controls, selection, fitOffset = 1.2) {
    const box = new THREE.Box3();
    for(const object of selection) box.expandByObject(object);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const maxSize = Math.max(size.x, size.y, size.z);
    const fitHeightDistance = maxSize / (2 * Math.atan(Math.PI * camera.fov / 360));
    const fitWidthDistance = fitHeightDistance / camera.aspect;
    const distance = fitOffset * Math.max(fitHeightDistance, fitWidthDistance);
    const direction = controls.target.clone().sub(camera.position).normalize().multiplyScalar(distance);
    controls.maxDistance = distance * 10;
    controls.target.copy(center);
    camera.near = distance / 100;
    camera.far = distance * 100;
    camera.updateProjectionMatrix();
    camera.position.copy(controls.target).sub(direction);
    controls.update();
}