import React from 'react'
import PropTypes from 'prop-types'
import './PropertyCard.css'

export const PropertyCard = ({ property, onSelect }) => {
  const handleClick = () => {
    onSelect(property.id)
  }

  const formatCurrency = (value) => {
    return `$${Number(value).toLocaleString()}`
  }

  return (
    <div className="property-card">
      <img src={property.image} alt="Property image" />
      <h2>{property.title}</h2>
      <p>{formatCurrency(property.price)}</p>
      <button onClick={handleClick}>View Details</button>
    </div>
  )
}

PropertyCard.propTypes = {
  property: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    title: PropTypes.string.isRequired,
    price: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    image: PropTypes.string.isRequired
  }).isRequired,
  onSelect: PropTypes.func.isRequired
}

export default PropertyCard
