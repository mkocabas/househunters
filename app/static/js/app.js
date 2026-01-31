/**
 * HouseHunters v2 - Frontend Application
 */

// State
const state = {
    searchType: null, // Will be detected from URL
    results: [],
    filteredResults: [], // Results after school filter applied
    sortColumn: null,
    sortDirection: 'asc',
    visibleColumns: [],
    mortgageSettings: {
        downPayment: 20,
        apr: 6.5,
        loanTerm: 30,
        propertyTax: 3000,
        insurance: 1500,
    },
    schoolRatingsLoading: false,
};

// Default columns to show
const DEFAULT_COLUMNS = [
    'address',
    'addressCity',
    'price',
    'beds',
    'baths',
    'area',
    'homeType',
    'schoolRatings',
];

// All available columns with display names
const ALL_COLUMNS = {
    address: 'Address',
    addressCity: 'City',
    addressState: 'State',
    addressZipcode: 'Zipcode',
    price: 'Price',
    beds: 'Beds',
    baths: 'Baths',
    area: 'Sqft',
    homeType: 'Type',
    statusText: 'Status',
    schoolRatings: 'Schools',
    zestimate: 'Zestimate',
    rentZestimate: 'Rent Estimate',
    rentDiff: 'Rent vs Estimate',
    daysOnZillow: 'Days Listed',
    yearBuilt: 'Year Built',
    lotAreaValue: 'Lot Size',
    taxAssessedValue: 'Tax Value',
    latitude: 'Latitude',
    longitude: 'Longitude',
    mortgageEstimate: 'Est. Mortgage',
};

// DOM Elements
const elements = {
    zillowUrl: document.getElementById('zillow-url'),
    searchTypeBadge: document.getElementById('search-type-badge'),
    searchTypeToggle: document.getElementById('search-type-toggle'),
    btnSale: document.getElementById('btn-sale'),
    btnRent: document.getElementById('btn-rent'),
    searchBtn: document.getElementById('search-btn'),
    mortgageSection: document.getElementById('mortgage-section'),
    priceLabel: document.getElementById('price-label'),
    tableContainer: document.querySelector('.table-container'),
    tableHeader: document.getElementById('table-header'),
    tableBody: document.getElementById('table-body'),
    resultsCount: document.getElementById('results-count'),
    emptyState: document.getElementById('empty-state'),
    loadingState: document.getElementById('loading-state'),
    columnsBtn: document.getElementById('columns-btn'),
    columnsModal: document.getElementById('columns-modal'),
    columnsList: document.getElementById('columns-list'),
    closeModal: document.getElementById('close-modal'),
    resetColumns: document.getElementById('reset-columns'),
    applyColumns: document.getElementById('apply-columns'),
    exportJsonBtn: document.getElementById('export-json-btn'),
    exportCsvBtn: document.getElementById('export-csv-btn'),
    // Filter inputs
    minBeds: document.getElementById('min-beds'),
    maxBeds: document.getElementById('max-beds'),
    minBaths: document.getElementById('min-baths'),
    maxBaths: document.getElementById('max-baths'),
    minPrice: document.getElementById('min-price'),
    maxPrice: document.getElementById('max-price'),
    minSqft: document.getElementById('min-sqft'),
    maxSqft: document.getElementById('max-sqft'),
    minYear: document.getElementById('min-year'),
    maxYear: document.getElementById('max-year'),
    // Mortgage inputs
    downPayment: document.getElementById('down-payment'),
    apr: document.getElementById('apr'),
    loanTerm: document.getElementById('loan-term'),
    propertyTax: document.getElementById('property-tax'),
    insurance: document.getElementById('insurance'),
    // School rating filters
    minElementary: document.getElementById('min-elementary'),
    minMiddle: document.getElementById('min-middle'),
    minHigh: document.getElementById('min-high'),
};

// Initialize
function init() {
    loadPreferences();
    setupEventListeners();
    // Trigger URL detection if there's a default value
    if (elements.zillowUrl.value) {
        handleUrlChange();
    }
}

function loadPreferences() {
    const savedColumns = localStorage.getItem('househunters_columns');
    if (savedColumns) {
        state.visibleColumns = JSON.parse(savedColumns);
    } else {
        state.visibleColumns = [...DEFAULT_COLUMNS];
    }

    const savedMortgage = localStorage.getItem('househunters_mortgage');
    if (savedMortgage) {
        state.mortgageSettings = JSON.parse(savedMortgage);
        elements.downPayment.value = state.mortgageSettings.downPayment;
        elements.apr.value = state.mortgageSettings.apr;
        elements.loanTerm.value = state.mortgageSettings.loanTerm;
        elements.propertyTax.value = state.mortgageSettings.propertyTax;
        elements.insurance.value = state.mortgageSettings.insurance;
    }
}

function savePreferences() {
    localStorage.setItem('househunters_columns', JSON.stringify(state.visibleColumns));
    localStorage.setItem('househunters_mortgage', JSON.stringify(state.mortgageSettings));
}

function setupEventListeners() {
    // URL input - detect search type on change
    elements.zillowUrl.addEventListener('input', handleUrlChange);
    elements.zillowUrl.addEventListener('paste', () => {
        setTimeout(handleUrlChange, 0);
    });

    // Search button
    elements.searchBtn.addEventListener('click', performSearch);

    // Mortgage input changes
    [elements.downPayment, elements.apr, elements.loanTerm, elements.propertyTax, elements.insurance].forEach(input => {
        input.addEventListener('change', () => {
            updateMortgageSettings();
            if (state.results.length > 0) {
                renderTable();
            }
        });
    });

    // Column management
    elements.columnsBtn.addEventListener('click', openColumnsModal);
    elements.closeModal.addEventListener('click', closeColumnsModal);
    elements.resetColumns.addEventListener('click', resetColumns);
    elements.applyColumns.addEventListener('click', applyColumns);
    elements.columnsModal.querySelector('.modal-backdrop').addEventListener('click', closeColumnsModal);

    // Export buttons
    elements.exportJsonBtn.addEventListener('click', () => exportResults('json'));
    elements.exportCsvBtn.addEventListener('click', () => exportResults('csv'));

    // Enter key on URL input
    elements.zillowUrl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && state.searchType) {
            performSearch();
        }
    });

    // Search type toggle buttons
    elements.btnSale.addEventListener('click', () => setSearchType('sale'));
    elements.btnRent.addEventListener('click', () => setSearchType('rent'));

    // School rating filter changes
    [elements.minElementary, elements.minMiddle, elements.minHigh].forEach(select => {
        select.addEventListener('change', applySchoolFilters);
    });
}

function handleUrlChange() {
    const url = elements.zillowUrl.value.trim();

    if (!url) {
        state.searchType = null;
        elements.searchTypeBadge.textContent = 'Paste a URL to start';
        elements.searchTypeBadge.className = 'badge';
        elements.searchBtn.disabled = true;
        elements.mortgageSection.classList.add('hidden');
        elements.searchTypeToggle.style.display = 'none';
        return;
    }

    // Check if URL contains valid Zillow search data
    if (url.includes('zillow.com')) {
        // Detect initial search type from URL
        const detectedType = detectSearchType(url);

        // Show toggle and set initial type
        elements.searchTypeToggle.style.display = 'block';
        elements.searchTypeBadge.textContent = 'Map bounds loaded from URL';
        elements.searchTypeBadge.className = 'badge';
        elements.searchBtn.disabled = false;

        // Set search type (detected or default to sale)
        setSearchType(detectedType || 'sale');
    } else {
        state.searchType = null;
        elements.searchTypeBadge.textContent = 'Invalid URL';
        elements.searchTypeBadge.className = 'badge';
        elements.searchBtn.disabled = true;
        elements.searchTypeToggle.style.display = 'none';
    }
}

function setSearchType(searchType) {
    state.searchType = searchType;

    // Update toggle buttons
    elements.btnSale.classList.toggle('active', searchType === 'sale');
    elements.btnRent.classList.toggle('active', searchType === 'rent');

    if (searchType === 'rent') {
        elements.mortgageSection.classList.add('hidden');
        elements.priceLabel.textContent = 'Monthly Rent';
        // Remove mortgage column for rent
        const mortgageIdx = state.visibleColumns.indexOf('mortgageEstimate');
        if (mortgageIdx > -1) state.visibleColumns.splice(mortgageIdx, 1);
        // Add rentDiff column for rent
        if (!state.visibleColumns.includes('rentDiff')) {
            state.visibleColumns.push('rentDiff');
        }
    } else {
        elements.mortgageSection.classList.remove('hidden');
        elements.priceLabel.textContent = 'Price';
        // Add mortgage column for sale
        if (!state.visibleColumns.includes('mortgageEstimate')) {
            state.visibleColumns.push('mortgageEstimate');
        }
        // Remove rentDiff column for sale
        const rentDiffIdx = state.visibleColumns.indexOf('rentDiff');
        if (rentDiffIdx > -1) state.visibleColumns.splice(rentDiffIdx, 1);
    }

    // Re-render table if we have results
    if (state.results.length > 0) {
        renderTable();
    }
}

function detectSearchType(url) {
    const lowerUrl = url.toLowerCase();

    // Check URL path
    if (lowerUrl.includes('/for_rent') || lowerUrl.includes('/rentals') || lowerUrl.includes('isforrent')) {
        return 'rent';
    }
    if (lowerUrl.includes('/for_sale') || lowerUrl.includes('/homes/') || lowerUrl.includes('isforsale')) {
        return 'sale';
    }

    // Try to parse searchQueryState
    try {
        const match = url.match(/searchQueryState=([^&]+)/);
        if (match) {
            const decoded = decodeURIComponent(match[1]);
            const state = JSON.parse(decoded);
            if (state.filterState?.isForRent?.value === true) {
                return 'rent';
            }
            return 'sale';
        }
    } catch (e) {
        // Ignore parse errors
    }

    // Default to sale if it looks like a Zillow URL
    if (lowerUrl.includes('zillow.com')) {
        return 'sale';
    }

    return null;
}

function updateMortgageSettings() {
    state.mortgageSettings = {
        downPayment: parseFloat(elements.downPayment.value) || 20,
        apr: parseFloat(elements.apr.value) || 6.5,
        loanTerm: parseInt(elements.loanTerm.value) || 30,
        propertyTax: parseFloat(elements.propertyTax.value) || 3000,
        insurance: parseFloat(elements.insurance.value) || 1500,
    };
    savePreferences();
}

function calculateMortgage(price) {
    const { downPayment, apr, loanTerm, propertyTax, insurance } = state.mortgageSettings;

    const downPaymentAmount = price * (downPayment / 100);
    const loanAmount = price - downPaymentAmount;
    const monthlyRate = (apr / 100) / 12;
    const numPayments = loanTerm * 12;

    let monthlyPI;
    if (monthlyRate === 0) {
        monthlyPI = loanAmount / numPayments;
    } else {
        monthlyPI = loanAmount * (monthlyRate * Math.pow(1 + monthlyRate, numPayments)) /
            (Math.pow(1 + monthlyRate, numPayments) - 1);
    }

    const monthlyTax = propertyTax / 12;
    const pmiRate = downPayment < 20 ? 0.005 : 0;
    const monthlyPMI = (loanAmount * pmiRate) / 12;
    const monthlyInsurance = insurance / 12;

    return monthlyPI + monthlyTax + monthlyPMI + monthlyInsurance;
}

async function performSearch() {
    const url = elements.zillowUrl.value.trim();
    if (!url || !state.searchType) {
        return;
    }

    const propertyTypes = {};
    // Send ALL property types with true/false values
    document.querySelectorAll('input[name="property_type"]').forEach(cb => {
        propertyTypes[cb.value] = cb.checked;
    });

    const requestBody = {
        zillow_url: url,
        search_type: state.searchType,
        min_beds: elements.minBeds.value ? parseInt(elements.minBeds.value) : null,
        max_beds: elements.maxBeds.value ? parseInt(elements.maxBeds.value) : null,
        min_baths: elements.minBaths.value ? parseInt(elements.minBaths.value) : null,
        max_baths: elements.maxBaths.value ? parseInt(elements.maxBaths.value) : null,
        min_price: elements.minPrice.value ? parseInt(elements.minPrice.value) : null,
        max_price: elements.maxPrice.value ? parseInt(elements.maxPrice.value) : null,
        min_sqft: elements.minSqft.value ? parseInt(elements.minSqft.value) : null,
        max_sqft: elements.maxSqft.value ? parseInt(elements.maxSqft.value) : null,
        min_year: elements.minYear.value ? parseInt(elements.minYear.value) : null,
        max_year: elements.maxYear.value ? parseInt(elements.maxYear.value) : null,
        property_types: propertyTypes,
    };

    showLoading(true);

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Search failed');
        }

        state.results = data.results || [];
        state.filteredResults = [...state.results];
        elements.resultsCount.textContent = `${state.results.length} properties`;

        if (state.results.length > 0) {
            renderTable();
            elements.tableContainer.classList.add('visible');
            elements.emptyState.classList.add('hidden');
            // Fetch school ratings progressively
            fetchSchoolRatings();
        } else {
            elements.tableContainer.classList.remove('visible');
            elements.emptyState.classList.remove('hidden');
            elements.emptyState.querySelector('h3').textContent = 'No Results';
            elements.emptyState.querySelector('p').textContent = 'No properties found matching your criteria.';
        }
    } catch (error) {
        console.error('Search error:', error);
        alert('Search failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function showLoading(show) {
    if (show) {
        elements.loadingState.classList.remove('hidden');
        elements.emptyState.classList.add('hidden');
        elements.tableContainer.classList.remove('visible');
        elements.searchBtn.disabled = true;
    } else {
        elements.loadingState.classList.add('hidden');
        elements.searchBtn.disabled = !state.searchType;
    }
}

function renderTable() {
    // Render header
    elements.tableHeader.innerHTML = '';
    state.visibleColumns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = ALL_COLUMNS[col] || col;
        th.dataset.column = col;

        const indicator = document.createElement('span');
        indicator.className = 'sort-indicator';
        th.appendChild(indicator);

        if (state.sortColumn === col) {
            th.classList.add(state.sortDirection === 'asc' ? 'sorted-asc' : 'sorted-desc');
        }

        th.addEventListener('click', () => sortBy(col));
        elements.tableHeader.appendChild(th);
    });

    // Sort results (use filteredResults)
    let sortedResults = [...state.filteredResults];
    if (state.sortColumn) {
        sortedResults.sort((a, b) => {
            let aVal = getNestedValue(a, state.sortColumn);
            let bVal = getNestedValue(b, state.sortColumn);

            if (state.sortColumn === 'mortgageEstimate') {
                aVal = calculateMortgage(getPrice(a));
                bVal = calculateMortgage(getPrice(b));
            }

            if (state.sortColumn === 'price') {
                aVal = getPrice(a);
                bVal = getPrice(b);
            }

            if (state.sortColumn === 'rentDiff') {
                const aRent = getPrice(a);
                const aEstimate = getNestedValue(a, 'rentZestimate');
                const bRent = getPrice(b);
                const bEstimate = getNestedValue(b, 'rentZestimate');
                aVal = (aRent && aEstimate) ? aRent - aEstimate : 0;
                bVal = (bRent && bEstimate) ? bRent - bEstimate : 0;
            }

            if (state.sortColumn === 'schoolRatings') {
                aVal = a.schoolRatingsTotal ?? -1;
                bVal = b.schoolRatingsTotal ?? -1;
            }

            if (state.sortColumn === 'daysOnZillow') {
                aVal = (aVal === null || aVal === undefined || aVal < 0) ? Infinity : aVal;
                bVal = (bVal === null || bVal === undefined || bVal < 0) ? Infinity : bVal;
            }

            if (typeof aVal === 'number' && typeof bVal === 'number') {
                return state.sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
            }

            const aNum = parseFloat(String(aVal).replace(/[^0-9.-]/g, ''));
            const bNum = parseFloat(String(bVal).replace(/[^0-9.-]/g, ''));
            if (!isNaN(aNum) && !isNaN(bNum)) {
                return state.sortDirection === 'asc' ? aNum - bNum : bNum - aNum;
            }

            aVal = String(aVal || '').toLowerCase();
            bVal = String(bVal || '').toLowerCase();
            return state.sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        });
    }

    // Render body
    elements.tableBody.innerHTML = '';
    sortedResults.forEach(property => {
        const tr = document.createElement('tr');
        tr.dataset.zpid = getZpid(property);
        tr.addEventListener('click', () => {
            const url = property.detailUrl;
            if (url) {
                window.open(url.startsWith('http') ? url : 'https://www.zillow.com' + url, '_blank');
            }
        });

        state.visibleColumns.forEach(col => {
            const td = document.createElement('td');
            td.className = col;

            let value = getNestedValue(property, col);

            if (col === 'price') {
                value = formatPrice(getPrice(property));
                td.classList.add('price');
            } else if (col === 'mortgageEstimate') {
                const mortgage = calculateMortgage(getPrice(property));
                value = formatPrice(mortgage) + '/mo';
                td.classList.add('mortgage');
            } else if (col === 'schoolRatings') {
                // Show loading spinner or rating
                if (property.schoolRatingsDisplay) {
                    td.textContent = property.schoolRatingsDisplay;
                } else {
                    const spinner = document.createElement('span');
                    spinner.className = 'cell-loading';
                    td.appendChild(spinner);
                }
                tr.appendChild(td);
                return; // Skip the default textContent assignment
            } else if (col === 'rentDiff') {
                const rentPrice = getPrice(property);
                const rentEstimate = getNestedValue(property, 'rentZestimate');
                if (rentEstimate && rentPrice) {
                    const diff = rentPrice - rentEstimate;
                    value = (diff >= 0 ? '+' : '') + formatPrice(diff);
                    td.style.color = diff < 0 ? 'var(--success)' : 'var(--danger)';
                } else {
                    value = '-';
                }
            } else if (col === 'daysOnZillow') {
                value = (value === null || value === undefined || value < 0) ? '-' : value;
            } else if (col === 'area' || col === 'lotAreaValue') {
                value = value ? formatNumber(value) : '-';
            } else if (col === 'homeType') {
                value = formatHomeType(value);
            } else if (col === 'zestimate' || col === 'rentZestimate' || col === 'taxAssessedValue') {
                value = value ? formatPrice(value) : '-';
            } else if (col === 'address') {
                td.classList.add('address');
                td.title = value || '';
            }

            td.textContent = value ?? '-';
            tr.appendChild(td);
        });

        elements.tableBody.appendChild(tr);
    });

    // Update count to show filtered
    const total = state.results.length;
    const filtered = state.filteredResults.length;
    if (filtered < total) {
        elements.resultsCount.textContent = `${filtered} of ${total} properties`;
    } else {
        elements.resultsCount.textContent = `${total} properties`;
    }
}

function sortBy(column) {
    if (state.sortColumn === column) {
        state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        state.sortColumn = column;
        state.sortDirection = 'asc';
    }
    renderTable();
}

function getNestedValue(obj, path) {
    const mappings = {
        addressCity: 'hdpData.homeInfo.city',
        homeType: 'hdpData.homeInfo.homeType',
        zestimate: 'hdpData.homeInfo.zestimate',
        rentZestimate: 'hdpData.homeInfo.rentZestimate',
        daysOnZillow: 'hdpData.homeInfo.daysOnZillow',
        yearBuilt: 'hdpData.homeInfo.yearBuilt',
        lotAreaValue: 'hdpData.homeInfo.lotAreaValue',
        taxAssessedValue: 'hdpData.homeInfo.taxAssessedValue',
        latitude: 'latLong.latitude',
        longitude: 'latLong.longitude',
    };

    // For fields with mappings, try the nested path first
    if (mappings[path]) {
        const nestedValue = mappings[path].split('.').reduce((o, k) => (o || {})[k], obj);
        if (nestedValue !== undefined && nestedValue !== null) {
            // For daysOnZillow, also check it's not negative
            if (path === 'daysOnZillow' && nestedValue < 0) {
                // fall through to check top-level
            } else {
                return nestedValue;
            }
        }
    }

    let value = path.split('.').reduce((o, k) => (o || {})[k], obj);

    if ((value === undefined || value === null) && path === 'addressCity') {
        const address = obj.address || '';
        const parts = address.split(',');
        if (parts.length >= 2) {
            value = parts[parts.length - 2]?.trim();
        }
    }

    return value;
}

function getPrice(property) {
    return property.unformattedPrice ||
        property.hdpData?.homeInfo?.price ||
        parseFloat(String(property.price || '0').replace(/[^0-9.-]/g, '')) ||
        0;
}

function formatPrice(value) {
    if (!value) return '-';
    return '$' + Math.round(value).toLocaleString();
}

function formatNumber(value) {
    if (!value) return '-';
    return Math.round(value).toLocaleString();
}

function formatHomeType(type) {
    const types = {
        SINGLE_FAMILY: 'Single Family',
        TOWNHOUSE: 'Townhouse',
        CONDO: 'Condo',
        MULTI_FAMILY: 'Multi-family',
        LAND: 'Land',
        MANUFACTURED: 'Manufactured',
        APARTMENT: 'Apartment',
    };
    return types[type] || type || '-';
}

function getZpid(property) {
    return property.zpid ||
        property.hdpData?.homeInfo?.zpid ||
        property.detailUrl?.match(/(\d+)_zpid/)?.[1] ||
        null;
}

async function fetchSchoolRatings() {
    if (state.schoolRatingsLoading) return;
    state.schoolRatingsLoading = true;

    for (const property of state.results) {
        const zpid = getZpid(property);
        if (!zpid || property.schoolRatingsDisplay) continue;

        try {
            const response = await fetch(`/api/details/${zpid}`);
            if (response.ok) {
                const data = await response.json();

                // Store school data on the property
                property.schoolRatings = data.schools;
                property.schoolRatingsTotal = data.schoolRatingsTotal;
                property.schoolRatingsDisplay = data.schoolRatingsDisplay;

                // Update the cell directly without full re-render
                const row = document.querySelector(`tr[data-zpid="${zpid}"]`);
                if (row) {
                    const cell = row.querySelector('td.schoolRatings');
                    if (cell) {
                        cell.innerHTML = '';
                        cell.textContent = data.schoolRatingsDisplay;
                    }
                }

                // Apply filters after each fetch
                applySchoolFilters();
            }
        } catch (error) {
            console.error(`Failed to fetch details for zpid ${zpid}:`, error);
            property.schoolRatingsDisplay = '-/-/-';
        }
    }

    state.schoolRatingsLoading = false;
}

function applySchoolFilters() {
    const minE = elements.minElementary.value ? parseInt(elements.minElementary.value) : null;
    const minM = elements.minMiddle.value ? parseInt(elements.minMiddle.value) : null;
    const minH = elements.minHigh.value ? parseInt(elements.minHigh.value) : null;

    // If no filters set, show all
    if (!minE && !minM && !minH) {
        state.filteredResults = [...state.results];
        renderTable();
        return;
    }

    state.filteredResults = state.results.filter(property => {
        const ratings = property.schoolRatings;

        // If school data not loaded yet, keep it (will be filtered when data arrives)
        if (!ratings) return true;

        // Check each filter
        if (minE && (ratings.elementary === null || ratings.elementary < minE)) {
            return false;
        }
        if (minM && (ratings.middle === null || ratings.middle < minM)) {
            return false;
        }
        if (minH && (ratings.high === null || ratings.high < minH)) {
            return false;
        }

        return true;
    });

    renderTable();
}

// Column Modal
function openColumnsModal() {
    elements.columnsList.innerHTML = '';

    Object.entries(ALL_COLUMNS).forEach(([key, label]) => {
        // Hide mortgage for rent, hide rentDiff for sale
        if (key === 'mortgageEstimate' && state.searchType === 'rent') return;
        if (key === 'rentDiff' && state.searchType === 'sale') return;

        const labelEl = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = key;
        checkbox.checked = state.visibleColumns.includes(key);

        labelEl.appendChild(checkbox);
        labelEl.appendChild(document.createTextNode(label));
        elements.columnsList.appendChild(labelEl);
    });

    elements.columnsModal.classList.add('visible');
}

function closeColumnsModal() {
    elements.columnsModal.classList.remove('visible');
}

function resetColumns() {
    state.visibleColumns = [...DEFAULT_COLUMNS];
    if (state.searchType === 'sale') {
        state.visibleColumns.push('mortgageEstimate');
    } else if (state.searchType === 'rent') {
        state.visibleColumns.push('rentDiff');
    }
    savePreferences();
    closeColumnsModal();
    if (state.results.length > 0) renderTable();
}

function applyColumns() {
    const checkboxes = elements.columnsList.querySelectorAll('input[type="checkbox"]:checked');
    state.visibleColumns = Array.from(checkboxes).map(cb => cb.value);
    savePreferences();
    closeColumnsModal();
    if (state.results.length > 0) renderTable();
}

// Export
async function exportResults(format) {
    if (state.results.length === 0) {
        alert('No results to export');
        return;
    }

    const exportData = state.results.map(property => {
        const row = { ...property };
        if (state.searchType === 'sale') {
            row.mortgageEstimate = Math.round(calculateMortgage(getPrice(property)));
        }
        return row;
    });

    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                results: exportData,
                format: format,
                columns: state.visibleColumns,
            }),
        });

        if (!response.ok) throw new Error('Export failed');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `properties.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    } catch (error) {
        console.error('Export error:', error);
        alert('Export failed: ' + error.message);
    }
}

document.addEventListener('DOMContentLoaded', init);
